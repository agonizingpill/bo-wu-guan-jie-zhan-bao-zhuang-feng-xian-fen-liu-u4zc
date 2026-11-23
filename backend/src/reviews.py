from fastapi import HTTPException

from .loans import active_loan, change_status, dossier
from .schemas import LoanStatus, ReviewStatus
from .storage import audit


def require_stage(db, loan_id, stage):
    active_loan(db, loan_id)
    row = db.execute('''SELECT r.* FROM unpack_review r JOIN triage_case t ON t.id=r.case_id
                       WHERE t.loan_id=%s''', (loan_id,)).fetchone()
    if not row or row['status'] != stage:
        raise HTTPException(409, '本批次未到该复核环节，请刷新档案')
    return row


def witness(db, loan_id, data, actor):
    row = require_stage(db, loan_id, ReviewStatus.AWAITING_WITNESS)
    db.execute('''UPDATE unpack_review SET status=%s,witness_by=%s,witness_note=%s,witnessed_at=now()
               WHERE case_id=%s''', (ReviewStatus.AWAITING_SUPERVISOR, actor, data.note, row['case_id']))
    audit(db, loan_id, actor, 'unpack_witnessed', observation=data.note)
    return dossier(db, loan_id)


def decide(db, loan_id, data, actor):
    row = require_stage(db, loan_id, ReviewStatus.AWAITING_SUPERVISOR)
    if row['witness_by'] == actor:
        raise HTTPException(403, '开箱见证与主管签字必须由不同人员完成')
    downgrade = data.verdict == 'downgrade'
    review_status = ReviewStatus.SAMPLING if downgrade else ReviewStatus.HELD
    db.execute('''UPDATE unpack_review SET status=%s,supervisor_by=%s,decision_reason=%s,decided_at=now()
               WHERE case_id=%s''', (review_status, actor, data.reason, row['case_id']))
    change_status(db, loan_id, LoanStatus.SAMPLING if downgrade else LoanStatus.HOLD)
    audit(db, loan_id, actor, 'downgrade_sample_required' if downgrade else 'unpack_held', reason=data.reason)
    return dossier(db, loan_id)


def sample(db, loan_id, data, actor):
    row = require_stage(db, loan_id, ReviewStatus.SAMPLING)
    if row['supervisor_by'] == actor:
        raise HTTPException(403, '主管签字与封签抽检须由不同人员完成')
    expected = db.execute('SELECT seal_code FROM crate_check WHERE loan_id=%s', (loan_id,)).fetchone()['seal_code']
    matched = data.seal_code == expected
    db.execute('''UPDATE unpack_review SET status=%s,sample_by=%s,sample_seal=%s,sampled_at=now() WHERE case_id=%s''',
               (ReviewStatus.CLEARED if matched else ReviewStatus.SAMPLING, actor, data.seal_code, row['case_id']))
    if matched:
        change_status(db, loan_id, LoanStatus.READY)
    audit(db, loan_id, actor, 'sample_cleared' if matched else 'sample_mismatch',
          observed=data.seal_code, expected=expected)
    return dossier(db, loan_id), None if matched else '实物封签与包装档案不符，抽检继续挂起'


def reopen(db, loan_id, data, actor):
    row = require_stage(db, loan_id, ReviewStatus.HELD)
    db.execute('''UPDATE unpack_review SET status=%s,witness_by=NULL,witness_note=NULL,witnessed_at=NULL,
                  supervisor_by=NULL,decision_reason=NULL,decided_at=NULL WHERE case_id=%s''',
               (ReviewStatus.AWAITING_WITNESS, row['case_id']))
    change_status(db, loan_id, LoanStatus.REVIEW_REQUIRED)
    audit(db, loan_id, actor, 'unpack_reopened', reason=data.reason)
    return dossier(db, loan_id)
