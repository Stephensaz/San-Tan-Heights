from pathlib import Path
from uuid import uuid4
import pytest
from src.operations.recovery.registry import RecoveryActionRegistry
from src.operations.recovery.framework import RecoveryCommandFramework
from src.operations.incidents.models import Incident
ROOT=Path(__file__).resolve().parents[3]
class C:
    rowcount=1
    def __init__(self,rows=None):self.rows=list(rows or []);self.sql=[]
    def execute(self,q,p=()):self.sql.append((q,p))
    def fetchone(self):return self.rows.pop(0) if self.rows else None
class Actions:
    def __init__(self):self.calls=0
    def execute(self,cursor,**kw):self.calls+=1;return {'status':'SUCCEEDED','action':kw['command_type']}
def inc(state='CONTAINED'):
    return Incident(uuid4(),'k','PUBLICATION_POINTER_INTEGRITY','ERROR',state,'INCIDENT_DETECTED')

def test_recovery_command_executes_once_and_records_history():
    reg=RecoveryActionRegistry.from_repository(ROOT); actions=Actions(); c=C()
    r=RecoveryCommandFramework(reg,actions).execute(c,incident=inc(),command_type='REVALIDATE_PUBLICATION_TARGET',payload={'property_id':str(uuid4()),'report_variant':'PUBLIC','channel':'WEB'},idempotency_key='abc',requested_by='operator')
    assert r.status=='SUCCEEDED' and actions.calls==1
    assert sum('recovery_command_history' in q for q,_ in c.sql)>=3

def test_recovery_command_rejects_missing_required_payload():
    reg=RecoveryActionRegistry.from_repository(ROOT)
    with pytest.raises(ValueError): RecoveryCommandFramework(reg,Actions()).execute(C(),incident=inc(),command_type='REQUEUE_REGENERATION_JOB',payload={},idempotency_key='x',requested_by='operator')

def test_idempotent_replay_does_not_execute_action_again():
    reg=RecoveryActionRegistry.from_repository(ROOT); actions=Actions(); i=inc(); payload={'job_id':str(uuid4())}
    from src.shared.hash import sha256_canonical
    h=sha256_canonical({'incident_id':str(i.incident_id),'command_type':'REQUEUE_REGENERATION_JOB','payload':payload})
    command_id=uuid4(); c=C(rows=[(command_id,h,'SUCCEEDED',{'action':'REQUEUE_REGENERATION_JOB'})])
    r=RecoveryCommandFramework(reg,actions).execute(c,incident=i,command_type='REQUEUE_REGENERATION_JOB',payload=payload,idempotency_key='same',requested_by='operator')
    assert r.status=='SUCCEEDED' and actions.calls==0
