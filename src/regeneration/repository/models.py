from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

ACTIVE_JOB_STATES = frozenset({'QUEUED','CLAIMED','RUNNING','RETRY_WAIT'})
JOB_STATES = frozenset({'QUEUED','CLAIMED','RUNNING','RETRY_WAIT','BLOCKED','STALE','SUCCEEDED','FAILED','CANCELLED','NO_OP'})
PRIORITY_CLASSES = frozenset({'CRITICAL','HIGH','NORMAL','BULK','LOW'})

@dataclass(frozen=True)
class RegenerationJob:
    job_id: UUID
    property_id: UUID
    report_variant: str
    trigger_type: str
    target_snapshot_id: UUID
    priority_class: str
    priority_score: int
    job_target_key: str
    correlation_id: UUID
    job_state: str = 'QUEUED'
    trigger_event_id: UUID | None = None
    old_report_id: UUID | None = None
    attempt_count: int = 0
    max_attempts: int = 3
    worker_id: str | None = None
    claimed_at: datetime | None = None
    last_heartbeat_at: datetime | None = None
    lease_expires_at: datetime | None = None
    queued_at: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    next_retry_at: datetime | None = None
    input_hash: str | None = None
    completion_report_id: UUID | None = None
    failure_stage: str | None = None
    failure_code: str | None = None
    failure_message_safe: str | None = None
    stale_reason_code: str | None = None
    release_id: UUID | None = None
