from uuid import uuid4
from src.operations.recovery.actions import ExplicitRecoveryActions
from src.operations.incidents.models import Incident
class C:
    def __init__(self,row=None):self.row=row;self.sql=[]
    def execute(self,q,p=()):self.sql.append((q,p))
    def fetchone(self):return self.row
class F:
    def __init__(self,result=True):self.result=result
    def release(self,cursor,freeze_id,actor):return self.result

def inc():return Incident(uuid4(),'k','PUBLICATION_POINTER_INTEGRITY','ERROR','CONTAINED','INCIDENT_DETECTED')
def test_release_publication_freeze_is_explicit():
    r=ExplicitRecoveryActions(freeze_repository=F()).execute(C(),incident=inc(),command_type='RELEASE_PUBLICATION_FREEZE',payload={'freeze_id':str(uuid4())},actor='operator')
    assert r['status']=='SUCCEEDED'
def test_requeue_job_only_targets_recoverable_terminal_states():
    c=C(row=(uuid4(),)); r=ExplicitRecoveryActions().execute(c,incident=inc(),command_type='REQUEUE_REGENERATION_JOB',payload={'job_id':str(uuid4())},actor='operator')
    assert r['status']=='SUCCEEDED'
    assert "IN ('FAILED','BLOCKED','STALE')" in c.sql[0][0]
