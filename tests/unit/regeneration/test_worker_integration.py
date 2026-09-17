from uuid import uuid4
from workers.regeneration_worker import RegenerationWorker, ReportBuildOutcome
from src.regeneration.repository.models import RegenerationJob

class Lease:
    def start(self,c,j,w): return True
    def claim_next(self,c,w): return None
    def heartbeat(self,c,j,w): return True
class Fresh:
    def __init__(self,status='FRESH',reason=None): self.status=status; self.reason=reason
    def check(self,*a,**k): return type('R',(),{'status':self.status,'reason_code':self.reason})()
class Repo:
    def __init__(self): self.actions=[]
    def mark_stale(self,c,j,w,r): self.actions.append(('STALE',r)); return True
    def set_terminal_failure(self,c,j,s,stage,code,msg,w): self.actions.append((s,stage,code)); return True
    def complete_success(self,c,j,w,r,h,state): self.actions.append((state,r,h)); return True
class Build:
    def __init__(self,reused=False,valid=True): self.reused=reused; self.valid=valid
    def build_and_persist(self,c,job): return ReportBuildOutcome(uuid4(),'a'*64,self.reused,self.valid,'REPORT_VALIDATION_FAILED' if not self.valid else None)

def job(): return RegenerationJob(uuid4(),uuid4(),'PUBLIC','REPORT_MARKED_DIRTY',uuid4(),'NORMAL',50,'b'*64,uuid4(),job_state='CLAIMED',worker_id='w',attempt_count=1)

def test_fresh_new_report_succeeds():
    r=Repo(); w=RegenerationWorker('w',Lease(),r,Fresh(),Build(False)); assert w.process(object(),job())=='SUCCEEDED'; assert r.actions[0][0]=='SUCCEEDED'
def test_fresh_reused_report_is_no_op():
    r=Repo(); w=RegenerationWorker('w',Lease(),r,Fresh(),Build(True)); assert w.process(object(),job())=='NO_OP'; assert r.actions[0][0]=='NO_OP'
def test_stale_job_never_builds():
    r=Repo(); w=RegenerationWorker('w',Lease(),r,Fresh('STALE','VARIANT_SEMANTIC_FINGERPRINT_CHANGED'),Build()); assert w.process(object(),job())=='STALE'; assert r.actions==[('STALE','VARIANT_SEMANTIC_FINGERPRINT_CHANGED')]
def test_blocked_job_never_builds():
    r=Repo(); w=RegenerationWorker('w',Lease(),r,Fresh('BLOCKED','CURRENT_SNAPSHOT_NOT_FOUND'),Build()); assert w.process(object(),job())=='BLOCKED'; assert r.actions[0][:2]==('BLOCKED','FRESHNESS')
