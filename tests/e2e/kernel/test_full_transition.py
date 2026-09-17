"""M1-016 kernel certification contract tests.

These tests exercise the complete application-level kernel with deterministic in-memory
transaction collaborators. PostgreSQL-specific locking, constraints, triggers and grants
are covered by persistence SQL tests and must also be run against a provisioned PostgreSQL
instance before production certification.
"""
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

from src.kernel.commands.models import IdempotencyDecision
from src.kernel.state import StateAdapterRegistry, StateRecord
from src.kernel.transitions import TransitionEngine, TransitionRequest

ROOT=Path(__file__).resolve().parents[3]

class Cursor: pass
class Adapter:
    entity_type='KERNEL_TEST_ENTITY'; state_dimension='CONTENT'
    def __init__(self,eid): self.r=StateRecord(eid,'BUILDING',1); self.applies=0
    def get_current_state(self,c,e): return self.r
    def lock_current_state(self,c,e): return self.r
    def apply_state(self,c,e,expected,target,version): self.applies+=1; self.r=StateRecord(e,target,version+1); return self.r
class Repo:
    def __init__(self): self.rows=[]
    def insert(self,c,r): self.rows.append(r)
class Events:
    def __init__(self): self.rows=[]
    def write(self,c,d): self.rows.append(d); return SimpleNamespace(event_id=uuid4())
class Idem:
    def __init__(self): self.rows={}
    def check(self,c,s,k,h):
        row=self.rows.get((s,k)); return IdempotencyDecision('REPLAY',row) if row else IdempotencyDecision('NEW')
    def record(self,c,r): self.rows[(r.service_name,r.idempotency_key)]=r

def build(eid):
    a=Adapter(eid); ar=StateAdapterRegistry(); ar.register(a); ev=Events(); tr=Repo(); gr=Repo(); idem=Idem()
    return TransitionEngine(ROOT,ar,event_writer=ev,transition_repository=tr,guard_repository=gr,idempotency_service=idem),a,ev,tr,gr

def request(eid,key='cert-1'):
    return TransitionRequest('KERNEL_TEST_BUILDING_TO_VALIDATING',eid,'KERNEL','SYSTEM','certifier','KERNEL',key,uuid4())

def test_sth_orch_kernel_001_success_and_idempotent_replay():
    eid=uuid4(); engine,adapter,events,transitions,guards=build(eid); c=Cursor(); r=request(eid)
    first=engine.execute(c,r); second=engine.execute(c,r)
    assert first.status=='APPLIED' and second.replayed
    assert adapter.r.state=='VALIDATING' and adapter.applies==1
    assert len(transitions.rows)==1
    assert [x.result for x in guards.rows]==['PASS','PASS','PASS']
    assert [e.event_type for e in events.rows]==['COMMAND_ACCEPTED','TRANSITION_APPLIED']
