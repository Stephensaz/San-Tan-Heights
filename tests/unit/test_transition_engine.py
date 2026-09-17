from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

from src.kernel.commands.models import IdempotencyDecision, ProcessedCommand
from src.kernel.state import StateAdapterRegistry, StateRecord, StateConflictError
from src.kernel.transitions import TransitionEngine, TransitionEngineInfrastructureError, TransitionRequest

ROOT=Path(__file__).resolve().parents[2]

class FakeCursor: pass

class MemoryAdapter:
    entity_type='KERNEL_TEST_ENTITY'; state_dimension='CONTENT'
    def __init__(self, state='BUILDING', version=1, exists=True, conflict=False):
        self.record=StateRecord(uuid4(),state,version) if exists else None
        self.conflict=conflict; self.applies=0
    def get_current_state(self,cursor,entity_id): return self.record
    def lock_current_state(self,cursor,entity_id): return self.record
    def apply_state(self,cursor,entity_id,expected_state,target_state,expected_version):
        if self.conflict: raise StateConflictError('race')
        if not self.record: raise RuntimeError('missing')
        if self.record.state != expected_state or self.record.state_version != expected_version:
            raise StateConflictError('race')
        self.applies += 1
        self.record=StateRecord(entity_id,target_state,expected_version+1)
        return self.record

class MemoryIdempotency:
    def __init__(self): self.rows={}
    def check(self,cursor,service,key,request_hash):
        row=self.rows.get((service,key))
        if row is None: return IdempotencyDecision('NEW')
        if row.request_hash != request_hash: raise RuntimeError('hash mismatch')
        return IdempotencyDecision('REPLAY',row)
    def record(self,cursor,command): self.rows[(command.service_name,command.idempotency_key)] = command

class MemoryEvents:
    def __init__(self, fail_on=None): self.drafts=[]; self.fail_on=fail_on
    def write(self,cursor,draft):
        if draft.event_type == self.fail_on: raise RuntimeError('forced event failure')
        self.drafts.append(draft)
        return SimpleNamespace(event_id=uuid4())

class MemoryRepo:
    def __init__(self): self.rows=[]
    def insert(self,cursor,row): self.rows.append(row)


def make_engine(adapter, events=None, idem=None):
    adapters=StateAdapterRegistry(); adapters.register(adapter)
    engine=TransitionEngine(ROOT, adapters,
        event_writer=events or MemoryEvents(),
        transition_repository=MemoryRepo(), guard_repository=MemoryRepo(),
        idempotency_service=idem or MemoryIdempotency())
    return engine


def req(entity_id, **kw):
    base=dict(transition_id='KERNEL_TEST_BUILDING_TO_VALIDATING',entity_id=entity_id,
              caller_id='KERNEL',actor_type='SYSTEM',actor_id='kernel-test',
              service_name='KERNEL',idempotency_key='idem-1',correlation_id=uuid4())
    base.update(kw); return TransitionRequest(**base)


def test_successful_transition_records_guards_events_and_command():
    entity=uuid4(); adapter=MemoryAdapter(); adapter.record=StateRecord(entity,'BUILDING',1)
    events=MemoryEvents(); idem=MemoryIdempotency(); engine=make_engine(adapter,events,idem)
    result=engine.execute(FakeCursor(),req(entity))
    assert result.status=='APPLIED' and result.state_version==2
    assert adapter.record.state=='VALIDATING'
    assert [e.event_type for e in events.drafts]==['COMMAND_ACCEPTED','TRANSITION_APPLIED']
    assert len(engine.transition_repository.rows)==1
    assert [g.result for g in engine.guard_repository.rows]==['PASS','PASS','PASS']
    assert len(idem.rows)==1


def test_failed_guard_is_audited_without_state_mutation():
    entity=uuid4(); adapter=MemoryAdapter(state='VALIDATING'); adapter.record=StateRecord(entity,'VALIDATING',2)
    events=MemoryEvents(); engine=make_engine(adapter,events)
    result=engine.execute(FakeCursor(),req(entity))
    assert result.status=='REJECTED'
    assert adapter.applies==0 and adapter.record.state=='VALIDATING'
    assert [e.event_type for e in events.drafts]==['COMMAND_ACCEPTED','TRANSITION_REJECTED','GUARD_FAILED']
    assert engine.transition_repository.rows[0].result=='REJECTED'
    assert [g.result for g in engine.guard_repository.rows]==['PASS','FAIL','NOT_EVALUATED']


def test_unauthorized_caller_rejected_before_state_access():
    entity=uuid4(); adapter=MemoryAdapter(); adapter.record=StateRecord(entity,'BUILDING',1)
    events=MemoryEvents(); engine=make_engine(adapter,events)
    result=engine.execute(FakeCursor(),req(entity,caller_id='RENDERER'))
    assert result.status=='REJECTED' and result.reason_code=='CALLER_NOT_AUTHORIZED'
    assert adapter.applies==0
    assert [e.event_type for e in events.drafts]==['COMMAND_ACCEPTED','UNAUTHORIZED_TRANSITION_ATTEMPT']
    assert engine.guard_repository.rows==[]


def test_duplicate_command_replays_without_second_mutation():
    entity=uuid4(); adapter=MemoryAdapter(); adapter.record=StateRecord(entity,'BUILDING',1)
    idem=MemoryIdempotency(); events=MemoryEvents(); engine=make_engine(adapter,events,idem)
    request=req(entity)
    first=engine.execute(FakeCursor(),request)
    second=engine.execute(FakeCursor(),request)
    assert first.status=='APPLIED'; assert second.status=='APPLIED' and second.replayed is True
    assert adapter.applies==1
    assert len(events.drafts)==2


def test_compare_and_swap_conflict_records_conflict_without_new_state():
    entity=uuid4(); adapter=MemoryAdapter(conflict=True); adapter.record=StateRecord(entity,'BUILDING',1)
    events=MemoryEvents(); engine=make_engine(adapter,events)
    result=engine.execute(FakeCursor(),req(entity))
    assert result.status=='CONFLICT'
    assert adapter.applies==0
    assert events.drafts[-1].event_type=='TRANSITION_REJECTED'


def test_event_persistence_failure_requires_transaction_rollback():
    entity=uuid4(); adapter=MemoryAdapter(); adapter.record=StateRecord(entity,'BUILDING',1)
    events=MemoryEvents(fail_on='TRANSITION_APPLIED'); engine=make_engine(adapter,events)
    with pytest.raises(TransitionEngineInfrastructureError):
        engine.execute(FakeCursor(),req(entity))
    # In a real DB transaction the preceding state update is rolled back by the caller.
    # The engine deliberately raises instead of converting this into an auditable success/failure row.
