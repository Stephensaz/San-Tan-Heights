from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID


@dataclass(frozen=True)
class ProcessedCommand:
    command_id: UUID
    service_name: str
    command_type: str
    idempotency_key: str
    request_hash: str
    result_status: str
    correlation_id: UUID
    result_payload: dict[str, Any] = field(default_factory=dict)
    processed_at: datetime | None = None


@dataclass(frozen=True)
class IdempotencyDecision:
    status: str
    prior: ProcessedCommand | None = None
