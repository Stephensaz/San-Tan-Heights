from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

@dataclass(frozen=True)
class QueueRegenerationCommand:
    property_id: UUID
    report_variant: str
    trigger_type: str
    report_schema_version: str
    content_contract_version: str
    variant_policy_version: str
    correlation_id: UUID
    idempotency_key: str
    service_name: str = 'REGENERATION_SERVICE'
    target_snapshot_id: UUID | None = None
    trigger_event_id: UUID | None = None
    old_report_id: UUID | None = None
    release_id: UUID | None = None
    change_class: str | None = None
    reason_code: str | None = None
    max_attempts: int = 3
    metadata: dict[str,Any] = field(default_factory=dict)

@dataclass(frozen=True)
class QueueRegenerationResult:
    status: str
    job_id: UUID | None
    target_snapshot_id: UUID | None
    job_target_key: str | None
    priority_class: str | None = None
    replayed: bool = False
