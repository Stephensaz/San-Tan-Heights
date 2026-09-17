from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from src.kernel.outbox import OutboxRepository


class EventPublisher(Protocol):
    def publish(self, *, event_id: str, topic: str) -> None: ...


@dataclass
class DispatchResult:
    claimed: int = 0
    delivered: int = 0
    retried: int = 0


class OutboxDispatcher:
    def __init__(self, repository: OutboxRepository | None = None, *, max_attempts: int = 5):
        self.repository = repository or OutboxRepository()
        self.max_attempts = max_attempts

    def dispatch_once(self, cursor, publisher: EventPublisher, worker_id: str,
                      batch_size: int = 50, lease_seconds: int = 60) -> DispatchResult:
        messages = self.repository.claim(cursor, worker_id, batch_size, lease_seconds)
        result = DispatchResult(claimed=len(messages))
        for message in messages:
            try:
                publisher.publish(event_id=str(message.event_id), topic=message.topic)
            except Exception as exc:  # boundary: convert external failure to safe retry metadata
                self.repository.mark_retry(
                    cursor, message.outbox_id, worker_id,
                    error_code=type(exc).__name__.upper()[:100],
                    safe_error='External event delivery failed.',
                    max_attempts=self.max_attempts,
                )
                result.retried += 1
            else:
                self.repository.mark_delivered(cursor, message.outbox_id, worker_id)
                result.delivered += 1
        return result
