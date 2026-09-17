from datetime import datetime, timezone
from uuid import uuid4
from src.kernel.audit import EventRepository, TransitionRepository, GuardRepository, OrchestrationEvent, StateTransitionRecord, GuardEvaluationRecord

class Cursor:
    def __init__(self): self.calls=[]
    def execute(self, sql, params): self.calls.append((sql,params))

def test_event_repository_insert_only():
    c=Cursor(); e=OrchestrationEvent(uuid4(),'COMMAND_ACCEPTED',1,datetime.now(timezone.utc),uuid4(),'SYSTEM','kernel','KERNEL',{'a':1},'a'*64)
    EventRepository().insert(c,e)
    assert len(c.calls)==1 and c.calls[0][0].lstrip().startswith('INSERT INTO audit.orchestration_events')

def test_transition_repository_insert_only():
    c=Cursor(); r=StateTransitionRecord(uuid4(),'TEST','TEST_ENTITY',uuid4(),'CONTENT','BUILDING','VALIDATING','APPLIED',uuid4(),'SYSTEM','kernel')
    TransitionRepository().insert(c,r)
    assert c.calls[0][0].lstrip().startswith('INSERT INTO audit.state_transitions')

def test_guard_repository_insert_only():
    c=Cursor(); r=GuardEvaluationRecord(uuid4(),'ENTITY_EXISTS',0,'PASS',uuid4())
    GuardRepository().insert(c,r)
    assert c.calls[0][0].lstrip().startswith('INSERT INTO audit.guard_evaluations')
