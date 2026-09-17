from __future__ import annotations

from uuid import UUID

from .repository import OutboxRepository


class TransactionalOutboxWriter:
    '''Writes outbox rows using the caller's existing database transaction/cursor.'''
    def __init__(self, repository: OutboxRepository | None = None):
        self.repository = repository or OutboxRepository()

    def enqueue(self, cursor, event_id: UUID, topics: list[str]) -> None:
        for topic in sorted(set(topics)):
            if not topic or not topic.strip():
                raise ValueError('topic must be non-empty')
            self.repository.insert(cursor, event_id, topic.strip())
