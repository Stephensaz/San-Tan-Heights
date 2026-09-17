from __future__ import annotations
from dataclasses import replace
from datetime import datetime, timezone
from uuid import uuid4

from src.kernel.audit.models import OrchestrationEvent
from src.shared.hash import sha256_canonical
from .event_model import EventDraft
from .event_registry import EventRegistry

class EventFactory:
    def __init__(self, registry: EventRegistry):
        self.registry = registry

    def create(self, draft: EventDraft) -> OrchestrationEvent:
        definition = self.registry.get(draft.event_type)
        occurred = draft.occurred_at or datetime.now(timezone.utc)
        if occurred.tzinfo is None:
            occurred = occurred.replace(tzinfo=timezone.utc)
        return OrchestrationEvent(
            event_id=uuid4(),
            event_type=draft.event_type,
            event_version=definition.version,
            occurred_at=occurred.astimezone(timezone.utc),
            correlation_id=draft.correlation_id,
            causation_event_id=draft.causation_event_id,
            actor_type=draft.actor_type,
            actor_id=draft.actor_id,
            source_system=draft.source_system,
            property_id=draft.property_id,
            report_id=draft.report_id,
            snapshot_id=draft.snapshot_id,
            job_id=draft.job_id,
            release_id=draft.release_id,
            reason_code=draft.reason_code,
            payload=draft.payload,
            payload_hash=sha256_canonical(draft.payload),
        )
