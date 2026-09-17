from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID

@dataclass(frozen=True)
class OrchestrationEvent:
    event_id: UUID
    event_type: str
    event_version: int
    occurred_at: datetime
    correlation_id: UUID
    actor_type: str
    actor_id: str
    source_system: str
    payload: dict[str, Any] = field(default_factory=dict)
    payload_hash: str = ''
    causation_event_id: UUID | None = None
    property_id: UUID | None = None
    report_id: UUID | None = None
    snapshot_id: UUID | None = None
    job_id: UUID | None = None
    release_id: UUID | None = None
    reason_code: str | None = None

@dataclass(frozen=True)
class StateTransitionRecord:
    transition_record_id: UUID
    transition_id: str
    entity_type: str
    entity_id: UUID
    state_dimension: str
    from_state: str
    to_state: str
    result: str
    correlation_id: UUID
    actor_type: str
    actor_id: str
    reason_code: str | None = None
    event_id: UUID | None = None

@dataclass(frozen=True)
class GuardEvaluationRecord:
    guard_evaluation_id: UUID
    guard_id: str
    ordinal: int
    result: str
    correlation_id: UUID
    transition_record_id: UUID | None = None
    reason_code: str | None = None
    safe_details: dict[str, Any] = field(default_factory=dict)
