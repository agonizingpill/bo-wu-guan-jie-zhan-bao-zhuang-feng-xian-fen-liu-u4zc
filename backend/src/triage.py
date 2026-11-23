import logging

from fastapi import HTTPException
from psycopg.types.json import Jsonb
from redis.exceptions import RedisError

from .loans import active_loan, change_status, dossier
from .schemas import LoanStatus
from .storage import QUEUE, audit, queue

FEATURES = ('material', 'packing', 'route_type', 'max_rh', 'transfers')


def enqueue(db, loan_id, actor):
    active_loan(db, loan_id)
    check = db.execute('SELECT * FROM crate_check WHERE loan_id=%s', (loan_id,)).fetchone()
    if not check:
        raise HTTPException(409, '请先完成包装检查')
    case = db.execute('SELECT id,status FROM triage_case WHERE loan_id=%s', (loan_id,)).fetchone()
    if case and case['status'] != 'failed':
        raise HTTPException(409, '此批次已进入风险分流，档案中可查看进度')
    snapshot = Jsonb({key: check[key] for key in FEATURES})
    if case:
        case_id = case['id']
        db.execute("UPDATE triage_case SET status='queued',input_snapshot=%s,error=NULL,requested_by=%s WHERE id=%s",
                   (snapshot, actor, case_id))
    else:
        case_id = db.execute('''INSERT INTO triage_case (loan_id,status,input_snapshot,requested_by)
                            VALUES (%s,'queued',%s,%s) RETURNING id''', (loan_id, snapshot, actor)).fetchone()['id']
    change_status(db, loan_id, LoanStatus.TRIAGE_PENDING)
    audit(db, loan_id, actor, 'triage_retried' if case else 'triage_queued', case_id=case_id)
    return dossier(db, loan_id), case_id


def notify_worker(case_id):
    try:
        with queue() as redis:
            redis.lpush(QUEUE, case_id)
    except RedisError:
        logging.exception('Redis enqueue failed; worker will recover the committed case')
