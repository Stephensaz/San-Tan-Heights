from pathlib import Path
from src.regeneration.retry import RetryPolicy, RegenerationRetryService
ROOT=Path(__file__).resolve().parents[3]

def test_retry_policy_is_fail_closed_and_exponential():
    p=RetryPolicy.from_repository(ROOT)
    assert p.classify('DB_TEMPORARY_FAILURE',1,3).action=='RETRY'
    assert p.classify('DB_TEMPORARY_FAILURE',1,3).delay_seconds==30
    assert p.classify('DB_TEMPORARY_FAILURE',2,3).delay_seconds==60
    assert p.classify('UNKNOWN_FAILURE',1,3).action=='BLOCK'

def test_retry_exhaustion_becomes_failed():
    p=RetryPolicy.from_repository(ROOT); d=p.classify('TIMEOUT',3,3)
    assert d.action=='FAIL' and d.rule_id=='RETRY_ATTEMPTS_EXHAUSTED'

def test_deterministic_business_failure_blocks():
    p=RetryPolicy.from_repository(ROOT)
    assert p.classify('SNAPSHOT_INVALID',1,3).action=='BLOCK'
    assert p.classify('CLASSIFICATION_VIOLATION',1,3).action=='BLOCK'

class Repo:
    def __init__(self): self.calls=[]
    def set_retry_wait(self,*args): self.calls.append(('retry',args)); return (1,3)
    def set_terminal_failure(self,*args): self.calls.append(('terminal',args)); return True

def test_retry_service_schedules_or_terminates_without_looping():
    r=Repo(); svc=RegenerationRetryService(ROOT,r); jid=__import__('uuid').uuid4()
    d=svc.handle_failure(object(),job_id=jid,worker_id='w',failure_stage='BUILD',failure_code='TIMEOUT',failure_message_safe='timeout',attempt_count=1,max_attempts=3)
    assert d.action=='RETRY' and r.calls[-1][0]=='retry'
    d=svc.handle_failure(object(),job_id=jid,worker_id='w',failure_stage='BUILD',failure_code='TIMEOUT',failure_message_safe='timeout',attempt_count=3,max_attempts=3)
    assert d.action=='FAIL' and r.calls[-1][0]=='terminal'
