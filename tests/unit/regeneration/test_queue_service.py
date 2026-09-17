from pathlib import Path
from uuid import uuid4
from src.regeneration.service import QueueRegenerationCommand, RegenerationQueueService
from src.kernel.commands import IdempotencyDecision
from src.snapshot.query import CurrentSnapshot
ROOT=Path(__file__).resolve().parents[3]

class Idem:
    def __init__(self,prior=None): self.prior=prior; self.recorded=[]
    def check(self,*a): return IdempotencyDecision('REPLAY',self.prior) if self.prior else IdempotencyDecision('NEW')
    def record(self,cursor,cmd): self.recorded.append(cmd)
class Repo:
    def __init__(self,active=None): self.active=active; self.inserted=[]
    def find_active(self,*a): return self.active
    def insert(self,c,j): self.inserted.append(j)
class Current:
    def __init__(self,pid,sid): self.v=CurrentSnapshot(pid,sid,1,'a'*64,'b'*64,'c'*64,'d'*64,'COMPLETE','PASS',None)
    def get(self,c,pid): return self.v if pid==self.v.property_id else None
class Events:
    def __init__(self): self.d=[]
    def write(self,c,d): self.d.append(d); return type('E',(),{'event_id':uuid4()})()

def cmd(pid,sid=None): return QueueRegenerationCommand(pid,'PUBLIC','REPORT_MARKED_DIRTY','report-1','content-1','variant-1',uuid4(),'idem-1',target_snapshot_id=sid,change_class='NORMAL_UPDATE')

def test_queue_creates_one_job_and_event():
    pid,sid=uuid4(),uuid4(); r=Repo(); i=Idem(); e=Events(); svc=RegenerationQueueService(ROOT,r,Current(pid,sid),i,e)
    out=svc.queue(object(),cmd(pid))
    assert out.status=='QUEUED' and len(r.inserted)==1 and len(e.d)==1
    assert r.inserted[0].target_snapshot_id==sid and r.inserted[0].priority_class=='NORMAL'
    assert e.d[0].event_type=='REGENERATION_JOB_QUEUED'

def test_queue_reuses_active_target():
    pid,sid,jid=uuid4(),uuid4(),uuid4(); r=Repo(jid); svc=RegenerationQueueService(ROOT,r,Current(pid,sid),Idem(),Events())
    out=svc.queue(object(),cmd(pid))
    assert out.status=='EXISTING_ACTIVE_JOB' and out.job_id==jid and not r.inserted

def test_explicit_noncurrent_target_blocks():
    pid,current,target=uuid4(),uuid4(),uuid4(); r=Repo(); svc=RegenerationQueueService(ROOT,r,Current(pid,current),Idem(),Events())
    out=svc.queue(object(),cmd(pid,target))
    assert out.status=='BLOCKED' and not r.inserted

def test_missing_current_snapshot_blocks():
    class NoneCurrent:
        def get(self,*a): return None
    pid=uuid4(); svc=RegenerationQueueService(ROOT,Repo(),NoneCurrent(),Idem(),Events())
    assert svc.queue(object(),cmd(pid)).status=='BLOCKED'
