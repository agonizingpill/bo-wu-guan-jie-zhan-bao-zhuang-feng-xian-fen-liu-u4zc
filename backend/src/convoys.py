from fastapi import HTTPException
from psycopg.errors import UniqueViolation
from psycopg.types.json import Jsonb

from .loans import active_loan, change_status, lock_loan
from .schemas import ConvoyStatus, LoanStatus
from .scoring import THRESHOLD
from .storage import audit
from .transit import lock_schedule

MEMBERS = '''
SELECT m.loan_id, m.added_by, m.added_at, l.accession, l.object_name, l.gallery, l.must_arrive,
       l.status AS loan_status, c.crate_code, c.seal_code, t.status AS triage_status, t.probability
FROM convoy_member m
JOIN exhibit_loan l ON l.id=m.loan_id
LEFT JOIN crate_check c ON c.loan_id=l.id
LEFT JOIN triage_case t ON t.loan_id=l.id
'''


def roster(db, convoy_id):
    return db.execute(MEMBERS + ' WHERE m.convoy_id=%s ORDER BY m.added_at,m.loan_id', (convoy_id,)).fetchall()


def lock_convoy(db, convoy_id):
    row = db.execute('SELECT * FROM convoy WHERE id=%s FOR UPDATE', (convoy_id,)).fetchone()
    if not row:
        raise HTTPException(404, '未找到车次')
    return row


def open_convoy(db, convoy_id):
    convoy = lock_convoy(db, convoy_id)
    if convoy['status'] != ConvoyStatus.OPEN:
        raise HTTPException(409, '该车次已派车，车单已封存')
    return convoy


def valid_assessment(db, convoy):
    # 只有按当前名单版本评估的记录可用；旧名单的评估记录不得抵用
    return db.execute('''SELECT * FROM convoy_assessment WHERE convoy_id=%s AND roster_version=%s
                         ORDER BY id DESC LIMIT 1''', (convoy['id'], convoy['roster_version'])).fetchone()


def window_conflict(db, convoy, members):
    galleries = list({member['gallery'] for member in members})
    loan_ids = [member['loan_id'] for member in members]
    return db.execute('''SELECT id,status,label,gallery FROM transit_window
        WHERE begins_at < %s AND ends_at > %s
          AND (loan_id IS NULL OR loan_id <> ALL(%s::bigint[]))
          AND ((status='setup' AND gallery = ANY(%s::text[]))
               OR (status IN ('booked','dispatched') AND (vehicle=%s OR gallery = ANY(%s::text[]))))
        ORDER BY CASE WHEN status='setup' THEN 0 ELSE 1 END,id LIMIT 1''',
        (convoy['ends_at'], convoy['begins_at'], loan_ids, galleries, convoy['vehicle'], galleries)).fetchone()


def conflict_reason(overlap):
    return (f"{overlap['gallery']}正在布置（{overlap['label']}），请改期" if overlap['status'] == 'setup'
            else '同一展厅或车辆已有运输窗口，请改期')


def hold_reasons(db, convoy, members):
    if not members:
        return ['车组还没有编入借品']
    reasons = []
    for member in members:
        if not member['seal_code']:
            reasons.append(f"{member['accession']} 缺少木箱封签，补录封签后才能派车")
        if member['loan_status'] != LoanStatus.READY:
            reasons.append(f"{member['accession']} 风险分流、开箱复核或抽检尚未放行")
        if member['must_arrive'] < convoy['ends_at']:
            reasons.append(f"{member['accession']} 到馆期限早于车组窗口结束时间")
    overlap = window_conflict(db, convoy, members)
    if overlap:
        reasons.append(conflict_reason(overlap))
    unscored = [member['accession'] for member in members if member['triage_status'] != 'scored']
    if unscored:
        reasons.append('等待风险出分：' + '、'.join(unscored))
    else:
        assessment = valid_assessment(db, convoy)
        if not assessment:
            stale = db.execute('SELECT 1 FROM convoy_assessment WHERE convoy_id=%s LIMIT 1',
                               (convoy['id'],)).fetchone()
            reasons.append('名单已变更，旧名单的评估记录不得抵用，请重新评估' if stale else '尚未评估同车合计风险')
        elif assessment['combined_risk'] >= THRESHOLD and convoy['signed_roster_version'] != convoy['roster_version']:
            reasons.append('同车合计风险达到开箱线，需主管签字')
    return reasons


def member_view(member):
    return {'loan_id': member['loan_id'], 'accession': member['accession'], 'object_name': member['object_name'],
            'gallery': member['gallery'], 'must_arrive': member['must_arrive'], 'loan_status': member['loan_status'],
            'crate_code': member['crate_code'], 'seal_code': member['seal_code'],
            'scored': member['triage_status'] == 'scored', 'probability': member['probability'],
            'added_at': member['added_at']}


def present(db, convoy, members=None):
    members = roster(db, convoy['id']) if members is None else members
    assessment = valid_assessment(db, convoy)
    combined = assessment['combined_risk'] if assessment else None
    dispatched = convoy['status'] == ConvoyStatus.DISPATCHED
    return {'id': convoy['id'], 'label': convoy['label'], 'vehicle': convoy['vehicle'],
            'begins_at': convoy['begins_at'], 'ends_at': convoy['ends_at'], 'status': convoy['status'],
            'roster_version': convoy['roster_version'], 'members': [member_view(m) for m in members],
            'combined_risk': combined, 'risk_threshold': assessment['threshold'] if assessment else THRESHOLD,
            'assessed_by': assessment['assessed_by'] if assessment else None,
            'assessed_at': assessment['assessed_at'] if assessment else None,
            'signature_required': combined is not None and combined >= THRESHOLD,
            'signed_by': convoy['signed_by'], 'signed_reason': convoy['signed_reason'],
            'signed_at': convoy['signed_at'], 'signed_roster_version': convoy['signed_roster_version'],
            'signature_valid': bool(convoy['signed_by']) and convoy['signed_roster_version'] == convoy['roster_version'],
            'hold_reasons': [] if dispatched else hold_reasons(db, convoy, members),
            'dispatch_order': db.execute('SELECT * FROM dispatch_order WHERE convoy_id=%s', (convoy['id'],)).fetchone(),
            'created_by': convoy['created_by'], 'created_at': convoy['created_at']}


def fleet(db):
    return [present(db, row) for row in db.execute('SELECT * FROM convoy ORDER BY begins_at,id').fetchall()]


def create(db, data, actor):
    row = db.execute('''INSERT INTO convoy (label,vehicle,begins_at,ends_at,created_by)
                        VALUES (%s,%s,%s,%s,%s) RETURNING *''',
                     (data.label, data.vehicle, data.begins_at, data.ends_at, actor)).fetchone()
    audit(db, None, actor, 'convoy_created', convoy_id=row['id'], label=data.label, vehicle=data.vehicle)
    return present(db, row, members=[])


def bump_roster(db, convoy, actor):
    # 增减借品即撤销整车签字，名单版本递增使旧评估记录失效
    row = db.execute('''UPDATE convoy SET roster_version=roster_version+1, signed_by=NULL, signed_reason=NULL,
                        signed_at=NULL, signed_roster_version=NULL, signed_roster=NULL WHERE id=%s RETURNING *''',
                     (convoy['id'],)).fetchone()
    if convoy['signed_by']:
        audit(db, None, actor, 'convoy_signature_revoked', convoy_id=convoy['id'], label=convoy['label'],
              previous_signed_by=convoy['signed_by'])
    return row


def add_member(db, convoy_id, data, actor):
    convoy = open_convoy(db, convoy_id)
    loan = active_loan(db, data.loan_id)
    if loan['must_arrive'] < convoy['ends_at']:
        raise HTTPException(409, '运输窗口不能越过借展到馆期限')
    lock_schedule(db)
    if db.execute('''SELECT 1 FROM convoy_member m JOIN convoy c ON c.id=m.convoy_id
                     WHERE m.loan_id=%s AND m.convoy_id<>%s AND c.status='open' LIMIT 1''',
                  (data.loan_id, convoy_id)).fetchone():
        raise HTTPException(409, '该批次已编入其他车次，请先移出')
    try:
        db.execute('INSERT INTO convoy_member (convoy_id,loan_id,added_by) VALUES (%s,%s,%s)',
                   (convoy_id, data.loan_id, actor))
    except UniqueViolation as exc:
        raise HTTPException(409, '该批次已在本车次中') from exc
    convoy = bump_roster(db, convoy, actor)
    audit(db, data.loan_id, actor, 'convoy_member_added', convoy_id=convoy_id, label=convoy['label'])
    return present(db, convoy)


def remove_member(db, convoy_id, loan_id, actor):
    convoy = open_convoy(db, convoy_id)
    removed = db.execute('DELETE FROM convoy_member WHERE convoy_id=%s AND loan_id=%s RETURNING loan_id',
                         (convoy_id, loan_id)).fetchone()
    if not removed:
        raise HTTPException(404, '该批次不在本车次中')
    convoy = bump_roster(db, convoy, actor)
    audit(db, loan_id, actor, 'convoy_member_removed', convoy_id=convoy_id, label=convoy['label'])
    return present(db, convoy)


def assess(db, convoy_id, actor):
    convoy = open_convoy(db, convoy_id)
    members = roster(db, convoy_id)
    if not members:
        raise HTTPException(409, '车组还没有编入借品，无法评估')
    unscored = [member['accession'] for member in members if member['triage_status'] != 'scored']
    if unscored:
        raise HTTPException(409, '等待风险出分：' + '、'.join(unscored))
    combined = min(1.0, sum(member['probability'] for member in members))
    snapshot = [{'loan_id': m['loan_id'], 'accession': m['accession']} for m in members]
    scores = [{'loan_id': m['loan_id'], 'accession': m['accession'], 'probability': m['probability']}
              for m in members]
    db.execute('''INSERT INTO convoy_assessment (convoy_id,roster_version,roster,member_scores,combined_risk,
                                                 threshold,assessed_by)
                  VALUES (%s,%s,%s,%s,%s,%s,%s)''',
               (convoy_id, convoy['roster_version'], Jsonb(snapshot), Jsonb(scores), combined, THRESHOLD, actor))
    audit(db, None, actor, 'convoy_assessed', convoy_id=convoy_id, roster_version=convoy['roster_version'],
          combined_risk=round(combined, 6), threshold=THRESHOLD)
    return present(db, convoy, members)


def sign(db, convoy_id, data, actor):
    convoy = open_convoy(db, convoy_id)
    assessment = valid_assessment(db, convoy)
    if not assessment:
        raise HTTPException(409, '请先按当前名单评估同车合计风险')
    if assessment['combined_risk'] < THRESHOLD:
        raise HTTPException(409, '合计风险未达开箱线，无需主管签字')
    if convoy['signed_roster_version'] == convoy['roster_version']:
        raise HTTPException(409, '当前名单已完成整车签字')
    members = roster(db, convoy_id)
    snapshot = [{'loan_id': m['loan_id'], 'accession': m['accession']} for m in members]
    convoy = db.execute('''UPDATE convoy SET signed_by=%s, signed_reason=%s, signed_at=now(),
                           signed_roster_version=%s, signed_roster=%s WHERE id=%s RETURNING *''',
                        (actor, data.reason, convoy['roster_version'], Jsonb(snapshot), convoy_id)).fetchone()
    audit(db, None, actor, 'convoy_signed', convoy_id=convoy_id, roster_version=convoy['roster_version'],
          combined_risk=assessment['combined_risk'], reason=data.reason)
    return present(db, convoy, members)


def dispatch(db, convoy_id, actor):
    convoy = lock_convoy(db, convoy_id)
    members = roster(db, convoy_id)
    if convoy['status'] == ConvoyStatus.DISPATCHED:
        order = db.execute('SELECT * FROM dispatch_order WHERE convoy_id=%s', (convoy_id,)).fetchone()
        return present(db, convoy, members), order, None
    for member in members:  # 锁顺序与登记窗口一致：车次 → 借展 → 排程
        lock_loan(db, member['loan_id'])
    lock_schedule(db)
    reasons = hold_reasons(db, convoy, members)
    if reasons:
        audit(db, None, actor, 'convoy_dispatch_blocked', convoy_id=convoy_id, reasons=reasons)
        return present(db, convoy, members), None, reasons
    assessment = valid_assessment(db, convoy)
    signed = convoy['signed_roster_version'] == convoy['roster_version']
    locked_roster = convoy['signed_roster'] if signed else [
        {'loan_id': m['loan_id'], 'accession': m['accession']} for m in members]
    order = db.execute('''INSERT INTO dispatch_order
        (convoy_id,roster,roster_version,combined_risk,signed_by,vehicle,begins_at,ends_at,issued_by)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (convoy_id) DO NOTHING RETURNING *''',
        (convoy_id, Jsonb(locked_roster), convoy['roster_version'], assessment['combined_risk'],
         convoy['signed_by'] if signed else None, convoy['vehicle'], convoy['begins_at'], convoy['ends_at'],
         actor)).fetchone()
    if not order:  # 同车已签发车单，重试不重复开单
        order = db.execute('SELECT * FROM dispatch_order WHERE convoy_id=%s', (convoy_id,)).fetchone()
        return present(db, convoy, members), order, None
    for member in members:
        db.execute("UPDATE transit_window SET status='superseded' WHERE loan_id=%s AND status IN ('booked','conflict')",
                   (member['loan_id'],))
        window = db.execute('''INSERT INTO transit_window (loan_id,gallery,vehicle,label,begins_at,ends_at,status,recorded_by)
            VALUES (%s,%s,%s,%s,%s,%s,'dispatched',%s) RETURNING id''',
            (member['loan_id'], member['gallery'], convoy['vehicle'], convoy['label'],
             convoy['begins_at'], convoy['ends_at'], actor)).fetchone()
        change_status(db, member['loan_id'], LoanStatus.DISPATCHED)
        audit(db, member['loan_id'], actor, 'dispatched', window_id=window['id'], vehicle=convoy['vehicle'],
              seal=member['seal_code'], convoy_id=convoy_id, dispatch_order=order['id'])
    convoy = db.execute("UPDATE convoy SET status='dispatched' WHERE id=%s RETURNING *", (convoy_id,)).fetchone()
    audit(db, None, actor, 'convoy_dispatched', convoy_id=convoy_id, dispatch_order=order['id'],
          vehicle=convoy['vehicle'], combined_risk=assessment['combined_risk'],
          roster=[item['accession'] for item in locked_roster])
    return present(db, convoy, roster(db, convoy_id)), order, None
