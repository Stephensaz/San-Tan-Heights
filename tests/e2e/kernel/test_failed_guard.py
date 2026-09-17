from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4
from src.kernel.commands.models import IdempotencyDecision
from src.kernel.state import StateAdapterRegistry, StateRecord
from src.kernel.transitions import TransitionEngine, TransitionRequest
ROOT=Path(__file__).resolve().parents[3]
class C: pass
class A:
 entity_type='KERNEL_TEST_ENTITY'; state_dimension='CONTENT'
 def __init__(self,e): self.r=StateRecord(e,'VALIDATING',2); self.applies=0
 def get_current_state(self,c,e): return self.r
 def lock_current_state(self,c,e): return self.r
 def apply_state(self,*a): self.applies+=1; return self.r
class R:
 def __init__(self): self.rows=[]
 def insert(self,c,r): self.rows.append(r)
class E:
 def __init__(self): self.rows=[]
 def write(self,c,d): self.rows.append(d); return SimpleNamespace(event_id=uuid4())
class I:
 def check(self,*a): return IdempotencyDecision('NEW')
 def record(self,*a): pass
def test_failed_guard_is_auditable_without_mutation():
 e=uuid4(); a=A(e); ar=StateAdapterRegistry(); ar.register(a); ev=E(); tr=R(); gr=R(); engine=TransitionEngine(ROOT,ar,event_writer=ev,transition_repository=tr,guard_repository=gr,idempotency_service=I())
 q=TransitionRequest('KERNEL_TEST_BUILDING_TO_VALIDATING',e,'KERNEL','SYSTEM','certifier','KERNEL','guard-1',uuid4())
 out=engine.execute(C(),q)
 assert out.status=='REJECTED' and a.applies==0
 assert [x.result for x in gr.rows]==['PASS','FAIL','NOT_EVALUATED']
 assert tr.rows[0].result=='REJECTED'
