from datetime import datetime,timezone,timedelta
from uuid import uuid4
from src.regeneration.worker import RegenerationLeaseManager
from src.regeneration.repository import RegenerationJobRepository

class Repo:
    def __init__(self): self.calls=[]
    def claim_next(self,c,w,e): self.calls.append(('claim',w,e)); return 'job'
    def start_running(self,c,j,w): self.calls.append(('start',j,w)); return True
    def heartbeat(self,c,j,w,e): self.calls.append(('heartbeat',j,w,e)); return True

def test_lease_claim_start_heartbeat_are_worker_scoped():
    r=Repo(); now=datetime(2026,1,1,tzinfo=timezone.utc); m=RegenerationLeaseManager(r,120); jid=uuid4()
    assert m.claim_next(object(),'worker-a',now)=='job'; assert r.calls[0][2]==now+timedelta(seconds=120)
    assert m.start(object(),jid,'worker-a'); assert m.heartbeat(object(),jid,'worker-a',now)

def test_repository_claim_contract_uses_skip_locked_and_priority_order():
    sql=RegenerationJobRepository.CLAIM_NEXT
    assert 'FOR UPDATE SKIP LOCKED' in sql
    assert 'priority_score DESC, queued_at ASC, job_id ASC' in sql
    assert "job_state='RETRY_WAIT'" in sql and 'next_retry_at <= now()' in sql

def test_heartbeat_requires_same_worker_running_and_unexpired_lease():
    sql=RegenerationJobRepository.HEARTBEAT
    assert 'worker_id=%s' in sql and "job_state='RUNNING'" in sql and 'lease_expires_at>now()' in sql
