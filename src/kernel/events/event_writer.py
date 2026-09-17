from __future__ import annotations
from pathlib import Path

from src.kernel.audit.repositories import EventRepository
from src.kernel.outbox import TransactionalOutboxWriter
from src.kernel.registry import load_registry_bundle
from .event_factory import EventFactory
from .event_model import EventDraft
from .event_registry import EventRegistry
from .event_validator import EventValidator

class EventWriter:
    '''Validates, persists and enqueues an event inside the caller's transaction.'''
    def __init__(self, root: Path, event_repository=None, outbox_writer=None):
        bundle = load_registry_bundle(root)
        self.registry = EventRegistry.from_repository(root)
        self.validator = EventValidator(root, self.registry, bundle.reason_codes)
        self.factory = EventFactory(self.registry)
        self.event_repository = event_repository or EventRepository()
        self.outbox_writer = outbox_writer or TransactionalOutboxWriter()

    def write(self, cursor, draft: EventDraft):
        self.validator.validate(draft)
        event = self.factory.create(draft)
        self.event_repository.insert(cursor, event)
        definition = self.registry.get(draft.event_type)
        self.outbox_writer.enqueue(cursor, event.event_id, list(definition.topics))
        return event
