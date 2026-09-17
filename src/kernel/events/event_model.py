from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID

@dataclass(frozen=True)
class EventDraft:
    event_type: str
    source_system: str
    actor_type: str
    actor_id: str
    correlation_id: UUID
    payload: dict[str, Any] = field(default_factory=dict)
    occurred_at: datetime | None = None
    causation_event_id: UUID | None = None
    property_id: UUID | None = None
    report_id: UUID | None = None
    snapshot_id: UUID | None = None
    job_id: UUID | None = None
    release_id: UUID | None = None
    reason_code: str | None = None
