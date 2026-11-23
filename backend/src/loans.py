from fastapi import HTTPException
from psycopg.errors import UniqueViolation

from .schemas import LoanStatus
from .storage import audit


ARCHIVE = '''
SELECT l.*, to_jsonb(c) AS crate, to_jsonb(w) AS transit, to_jsonb(t) AS triage,
       to_jsonb(r) AS review
FROM exhibit_loan l
LEFT JOIN crate_check c ON c.loan_id=l.id
LEFT JOIN transit_window w ON w.loan_id=l.id AND w.status IN ('booked','conflict','dispatched')
LEFT JOIN triage_case t ON t.loan_id=l.id
LEFT JOIN unpack_review r ON r.case_id=t.id
'''


def dispatch_issue(record):
    if record['status'] == LoanStatus.DISPATCHED:
        return '这笔借展已派车'
    if not record['crate'] or not record['crate']['seal_code']:
        return '缺少木箱封签，补录封签后才能派车'
    window = record['transit']
    if not window:
        return '请先登记运输窗口'
    if window['status'] == 'conflict':
        return window['conflict_reason']
    if record['status'] != LoanStatus.READY:
        return '风险分流、开箱复核或抽检尚未放行'
    return None


def present(record):
    return {**record, 'dispatch_issue': dispatch_issue(record)}


def archive(db):
    return [present(row) for row in db.execute(ARCHIVE + ' ORDER BY l.must_arrive,l.id').fetchall()]


def dossier(db, loan_id):
    row = db.execute(ARCHIVE + ' WHERE l.id=%s', (loan_id,)).fetchone()
    if not row:
        raise HTTPException(404, '未找到借展批次')
    return {**present(row), 'history': db.execute('''SELECT actor,action,details,recorded_at
          FROM audit_entry WHERE loan_id=%s ORDER BY id DESC''', (loan_id,)).fetchall()}


def lock_loan(db, loan_id):
    row = db.execute('SELECT * FROM exhibit_loan WHERE id=%s FOR UPDATE', (loan_id,)).fetchone()
    if not row:
        raise HTTPException(404, '未找到借展批次')
    return row


def active_loan(db, loan_id):
    loan = lock_loan(db, loan_id)
    if loan['status'] == LoanStatus.DISPATCHED:
        raise HTTPException(409, '该批次已派车，档案已封存')
    return loan


def change_status(db, loan_id, status):
    db.execute('UPDATE exhibit_loan SET status=%s WHERE id=%s', (status, loan_id))


def register(db, data, actor):
    try:
        row = db.execute('''INSERT INTO exhibit_loan (accession,object_name,lender,gallery,must_arrive)
             VALUES (%(accession)s,%(object_name)s,%(lender)s,%(gallery)s,%(must_arrive)s) RETURNING id''',
                         data.model_dump()).fetchone()
    except UniqueViolation as exc:
        raise HTTPException(409, '该借展单号已经登记') from exc
    audit(db, row['id'], actor, 'loan_registered', accession=data.accession)
    return dossier(db, row['id'])


def inspect_crate(db, loan_id, data, actor):
    loan = active_loan(db, loan_id)
    current = db.execute('SELECT * FROM crate_check WHERE loan_id=%s', (loan_id,)).fetchone()
    case = db.execute('''SELECT t.status,r.status AS review_status FROM triage_case t
                          LEFT JOIN unpack_review r ON r.case_id=t.id WHERE t.loan_id=%s''', (loan_id,)).fetchone()
    fields = data.model_dump(mode='json')
    if case and case['status'] != 'failed':
        if any(current[key] != value for key, value in fields.items() if key != 'seal_code'):
            raise HTTPException(409, '已生成风险输入快照，仅允许补录封签')
        if case['review_status'] == 'cleared' and current['seal_code'] != data.seal_code:
            raise HTTPException(409, '该封签已通过抽检，不能修改')
    try:
        db.execute('''INSERT INTO crate_check (loan_id,crate_code,seal_code,material,packing,route_type,max_rh,transfers,noted_by)
              VALUES (%(loan_id)s,%(crate_code)s,%(seal_code)s,%(material)s,%(packing)s,%(route_type)s,%(max_rh)s,%(transfers)s,%(actor)s)
              ON CONFLICT (loan_id) DO UPDATE SET crate_code=excluded.crate_code, seal_code=excluded.seal_code,
                material=excluded.material, packing=excluded.packing, route_type=excluded.route_type,
                max_rh=excluded.max_rh, transfers=excluded.transfers, noted_by=excluded.noted_by,updated_at=now()''',
                   {**fields, 'loan_id': loan_id, 'actor': actor})
    except UniqueViolation as exc:
        raise HTTPException(409, '箱号或封签已被另一个借展批次占用') from exc
    if loan['status'] == LoanStatus.REGISTERED:
        change_status(db, loan_id, LoanStatus.PACKING)
    audit(db, loan_id, actor, 'crate_checked', crate_code=data.crate_code, seal_code=data.seal_code,
          previous_seal=current['seal_code'] if current else None,
          issue=None if data.seal_code else 'missing_seal')
    return dossier(db, loan_id)
