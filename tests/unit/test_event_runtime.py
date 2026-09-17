from pathlib import Path
from uuid import uuid4
import pytest

from src.kernel.events import EventDraft, EventRegistry, EventValidator, EventValidationError, EventFactory, EventWriter
from src.kernel.registry import load_registry_bundle

ROOT=Path(__file__).resolve().parents[2]

class Cursor:
    def __init__(self): self.calls=[]
    def execute(self,sql,params=None): self.calls.append((sql,params))


def test_event_registry_loads_known_event():
    reg=EventRegistry.from_repository(ROOT)
    d=reg.get('TRANSITION_APPLIED')
    assert d.version == 1 and 'KERNEL' in d.producers


def test_event_validator_rejects_unknown_event():
    bundle=load_registry_bundle(ROOT); reg=EventRegistry.from_repository(ROOT)
    val=EventValidator(ROOT,reg,bundle.reason_codes)
    with pytest.raises(EventValidationError):
        val.validate(EventDraft('NOPE','KERNEL','SYSTEM','kernel',uuid4(),{}))


def test_event_validator_rejects_wrong_producer():
    bundle=load_registry_bundle(ROOT); reg=EventRegistry.from_repository(ROOT)
    val=EventValidator(ROOT,reg,bundle.reason_codes)
    with pytest.raises(EventValidationError):
        val.validate(EventDraft('TRANSITION_APPLIED','RENDERER','SYSTEM','renderer',uuid4(),{}))


def test_event_validator_rejects_unknown_reason():
    bundle=load_registry_bundle(ROOT); reg=EventRegistry.from_repository(ROOT)
    val=EventValidator(ROOT,reg,bundle.reason_codes)
    with pytest.raises(EventValidationError):
        val.validate(EventDraft('TRANSITION_APPLIED','KERNEL','SYSTEM','kernel',uuid4(),{},reason_code='NOPE'))


def test_event_factory_hash_is_deterministic():
    reg=EventRegistry.from_repository(ROOT); factory=EventFactory(reg); corr=uuid4()
    a=factory.create(EventDraft('TRANSITION_APPLIED','KERNEL','SYSTEM','kernel',corr,{'b':2,'a':1}))
    b=factory.create(EventDraft('TRANSITION_APPLIED','KERNEL','SYSTEM','kernel',corr,{'a':1,'b':2}))
    assert a.payload_hash == b.payload_hash


def test_event_writer_persists_event_then_outbox_in_caller_cursor():
    c=Cursor(); corr=uuid4()
    event=EventWriter(ROOT).write(c, EventDraft('TRANSITION_APPLIED','KERNEL','SYSTEM','kernel',corr,{'transition_id':'T1'},reason_code='KERNEL_TEST_TRANSITION'))
    assert event.event_type == 'TRANSITION_APPLIED'
    assert len(c.calls)==2
    assert 'INSERT INTO audit.orchestration_events' in c.calls[0][0]
    assert 'INSERT INTO audit.event_outbox' in c.calls[1][0]
    assert c.calls[1][1][1]=='events'
