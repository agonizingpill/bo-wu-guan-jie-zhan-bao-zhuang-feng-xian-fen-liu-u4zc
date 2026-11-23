from fastapi import HTTPException
from psycopg.errors import UniqueViolation

from .loans import active_loan, change_status, dispatch_issue, dossier
from .schemas import LoanStatus
from .storage import audit


def lock_schedule(db):
    db.execute('SELECT pg_advisory_xact_lock(66002)')


def schedule(db):
    return db.execute('''SELECT w.*, l.accession FROM transit_window w
                        LEFT JOIN exhibit_loan l ON l.id=w.loan_id
                        WHERE w.status <> 'superseded' ORDER BY w.begins_at,w.id''').fetchall()


def block_gallery(db, data, actor):
    lock_schedule(db)
    if db.execute('''SELECT 1 FROM transit_window WHERE gallery=%s AND status IN ('booked','dispatched')
                     AND begins_at < %s AND ends_at > %s LIMIT 1''',
                  (data.gallery, data.ends_at, data.begins_at)).fetchone():
        raise HTTPException(409, '与已确认的运输窗口重叠，请调整布置时间')
    try:
        row = db.execute('''INSERT INTO transit_window (gallery,label,begins_at,ends_at,status,recorded_by)
                        VALUES (%s,%s,%s,%s,'setup',%s) RETURNING *''',
                         (data.gallery, data.label, data.begins_at, data.ends_at, actor)).fetchone()
    except UniqueViolation as exc:
        raise HTTPException(409, '该展厅已登记相同布置窗口') from exc
    audit(db, None, actor, 'gallery_setup', window_id=row['id'], gallery=data.gallery, label=data.label)
    return row


def reserve(db, loan_id, data, actor):
    loan = active_loan(db, loan_id)
    if data.ends_at > loan['must_arrive']:
        raise HTTPException(409, '运输窗口不能越过借展到馆期限')
    lock_schedule(db)
    overlap = db.execute('''SELECT id,status,label,gallery FROM transit_window
        WHERE loan_id IS DISTINCT FROM %s AND begins_at < %s AND ends_at > %s
          AND ((status='setup' AND gallery=%s) OR (status IN ('booked','dispatched') AND (vehicle=%s OR gallery=%s)))
        ORDER BY CASE WHEN status='setup' THEN 0 ELSE 1 END,id LIMIT 1''',
        (loan_id, data.ends_at, data.begins_at, loan['gallery'], data.vehicle, loan['gallery'])).fetchone()
    if overlap:
        reason = (f"{overlap['gallery']}正在布置（{overlap['label']}），请改期" if overlap['status'] == 'setup'
                  else '同一展厅或车辆已有运输窗口，请改期')
    else:
        reason = None
    previous = db.execute('''UPDATE transit_window SET status='superseded' WHERE loan_id=%s
                          AND status IN ('booked','conflict') RETURNING id''', (loan_id,)).fetchone()
    row = db.execute('''INSERT INTO transit_window (loan_id,gallery,vehicle,label,begins_at,ends_at,status,conflict_reason,recorded_by)
         VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id''',
                     (loan_id, loan['gallery'], data.vehicle, loan['accession'], data.begins_at, data.ends_at,
                      'conflict' if overlap else 'booked', reason, actor)).fetchone()
    audit(db, loan_id, actor, 'window_conflict' if overlap else 'window_reserved', window_id=row['id'],
          previous_window=previous['id'] if previous else None, reason=reason,
          conflict_window=overlap['id'] if overlap else None)
    return dossier(db, loan_id)


def dispatch(db, loan_id, actor):
    active_loan(db, loan_id)
    lock_schedule(db)
    record = dossier(db, loan_id)
    reason = dispatch_issue(record)
    if reason:
        audit(db, loan_id, actor, 'dispatch_blocked', reason=reason)
        return record, reason
    window = record['transit']
    db.execute("UPDATE transit_window SET status='dispatched' WHERE id=%s", (window['id'],))
    change_status(db, loan_id, LoanStatus.DISPATCHED)
    audit(db, loan_id, actor, 'dispatched', window_id=window['id'], vehicle=window['vehicle'],
          seal=record['crate']['seal_code'])
    return dossier(db, loan_id), None
