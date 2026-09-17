from __future__ import annotations

from .idempotency_repository import ProcessedCommandRepository
from .models import IdempotencyDecision, ProcessedCommand


class IdempotencyConflict(RuntimeError):
    code = 'IDEMPOTENCY_KEY_PAYLOAD_MISMATCH'


class IdempotencyService:
    def __init__(self, repository: ProcessedCommandRepository | None = None):
        self.repository = repository or ProcessedCommandRepository()

    def check(self, cursor, service_name: str, idempotency_key: str, request_hash: str) -> IdempotencyDecision:
        prior = self.repository.get(cursor, service_name, idempotency_key)
        if prior is None:
            return IdempotencyDecision(status='NEW')
        if prior.request_hash != request_hash:
            raise IdempotencyConflict(
                f'idempotency key already used by {service_name} with a different request hash'
            )
        return IdempotencyDecision(status='REPLAY', prior=prior)

    def record(self, cursor, command: ProcessedCommand) -> None:
        self.repository.insert(cursor, command)
