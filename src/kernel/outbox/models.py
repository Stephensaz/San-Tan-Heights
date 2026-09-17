from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class OutboxMessage:
    outbox_id: UUID
    event_id: UUID
    topic: str
    delivery_state: str = 'PENDING'
    attempt_count: int = 0
    claimed_by: str | None = None
    lease_expires_at: datetime | None = None


@dataclass(frozen=True)
class EventConsumption:
    consumer_name: str
    event_id: UUID
    result_hash: str | None = None
