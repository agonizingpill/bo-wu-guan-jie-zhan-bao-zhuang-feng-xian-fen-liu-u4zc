import logging
import time
from pathlib import Path

from psycopg import Error as DatabaseError
from psycopg.types.json import Jsonb
from redis.exceptions import RedisError

from .loans import change_status, lock_loan
from .schemas import LoanStatus
from .scoring import score
from .storage import QUEUE, audit, connection, initialize, queue

HEARTBEAT = Path('/tmp/museum-heartbeat')


def process(case_id):
    with connection() as db:
        reference = db.execute('SELECT loan_id FROM triage_case WHERE id=%s', (case_id,)).fetchone()
        if not reference:
            return
        loan_id = reference['loan_id']
        lock_loan(db, loan_id)
        case = db.execute('SELECT * FROM triage_case WHERE id=%s', (case_id,)).fetchone()
        if case['status'] != 'queued':
            return
        try:
            probability, risk, evidence = score(case['input_snapshot'])
        except Exception as exc:
            logging.exception('Model failed to score case %s', case_id)
            db.execute("UPDATE triage_case SET status='failed',error=%s,attempts=attempts+1 WHERE id=%s",
                       ('模型计算失败。请检查包装快照后重试。', case_id))
            change_status(db, loan_id, LoanStatus.PACKING)
            audit(db, loan_id, 'worker', 'triage_failed', case_id=case_id, error_type=type(exc).__name__)
            return
        db.execute('''UPDATE triage_case SET status='scored', probability=%s, risk=%s, evidence=%s,
                       attempts=attempts+1,computed_at=now(),error=NULL WHERE id=%s''',
                   (probability, risk, Jsonb(evidence), case_id))
        if risk == 'high':
            db.execute("INSERT INTO unpack_review (case_id,status) VALUES (%s,'awaiting_witness')", (case_id,))
        change_status(db, loan_id, LoanStatus.REVIEW_REQUIRED if risk == 'high' else LoanStatus.READY)
        audit(db, loan_id, 'worker', 'triage_scored', case_id=case_id, risk=risk, probability=probability)
        print(f'case={case_id} loan={loan_id} risk={risk} probability={probability:.6f}', flush=True)


def recover_queue(redis):
    # PostgreSQL keeps the pending intent if a producer or worker exits before completion.
    with connection() as db:
        pending = db.execute("SELECT id FROM triage_case WHERE status='queued' ORDER BY id LIMIT 100").fetchall()
    if pending:
        redis.lpush(QUEUE, *(row['id'] for row in pending))


def main():
    initialize()
    with queue() as redis:
        while True:
            try:
                message = redis.brpop(QUEUE, timeout=2)
                if message:
                    process(int(message[1]))
                else:
                    recover_queue(redis)
                HEARTBEAT.touch()
            except (DatabaseError, RedisError, ValueError):
                logging.exception('Queue operation failed')
                time.sleep(2)


if __name__ == '__main__':
    main()
