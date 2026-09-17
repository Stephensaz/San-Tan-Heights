from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping
from uuid import UUID, uuid4

from src.kernel.audit.models import GuardEvaluationRecord, StateTransitionRecord
from src.kernel.audit.repositories import GuardRepository, TransitionRepository
from src.kernel.commands import IdempotencyService, ProcessedCommand
from src.kernel.commands.idempotency_service import IdempotencyConflict
from src.kernel.events import EventDraft, EventWriter
from src.kernel.guards import GuardContext, GuardRunner
from src.kernel.state import EntityNotFoundError, StateAdapterRegistry, StateConflictError
from src.kernel.transitions.transition_authorization import TransitionAuthorizationError, TransitionAuthorizer
from src.kernel.transitions.transition_registry import TransitionRegistry, TransitionRegistryError
from src.shared.hash import sha256_canonical


RESULTS = frozenset({'APPLIED', 'REJECTED', 'BLOCKED', 'NO_OP', 'CONFLICT', 'FAILED'})


class TransitionEngineError(RuntimeError):
    pass


class TransitionEngineInfrastructureError(TransitionEngineError):
    """Raised when an infrastructure failure requires the caller transaction to roll back."""


@dataclass(frozen=True)
class TransitionRequest:
    transition_id: str
    entity_id: UUID
    caller_id: str
    actor_type: str
    actor_id: str
    service_name: str
    idempotency_key: str
    correlation_id: UUID
    command_type: str = 'EXECUTE_TRANSITION'
    causation_event_id: UUID | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def semantic_payload(self) -> dict[str, Any]:
        return {
            'transition_id': self.transition_id,
            'entity_id': str(self.entity_id),
            'caller_id': self.caller_id,
            'actor_type': self.actor_type,
            'actor_id': self.actor_id,
            'service_name': self.service_name,
            'command_type': self.command_type,
            'metadata': dict(self.metadata),
        }


@dataclass(frozen=True)
class TransitionResult:
    status: str
    transition_id: str
    entity_id: UUID
    from_state: str | None = None
    to_state: str | None = None
    state_version: int | None = None
    reason_code: str | None = None
    event_id: UUID | None = None
    replayed: bool = False

    def __post_init__(self) -> None:
        if self.status not in RESULTS:
            raise ValueError(f'unsupported transition result: {self.status}')

    def to_payload(self) -> dict[str, Any]:
        return {
            'status': self.status,
            'transition_id': self.transition_id,
            'entity_id': str(self.entity_id),
            'from_state': self.from_state,
            'to_state': self.to_state,
            'state_version': self.state_version,
            'reason_code': self.reason_code,
            'event_id': str(self.event_id) if self.event_id else None,
        }

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any], replayed: bool = False) -> 'TransitionResult':
        event_id = payload.get('event_id')
        return cls(
            status=payload['status'],
            transition_id=payload['transition_id'],
            entity_id=UUID(str(payload['entity_id'])),
            from_state=payload.get('from_state'),
            to_state=payload.get('to_state'),
            state_version=payload.get('state_version'),
            reason_code=payload.get('reason_code'),
            event_id=UUID(str(event_id)) if event_id else None,
            replayed=replayed,
        )


class TransitionEngine:
    def __init__(
        self,
        root: Path,
        state_adapters: StateAdapterRegistry,
        transition_registry: TransitionRegistry | None = None,
        authorizer: TransitionAuthorizer | None = None,
        guard_runner: GuardRunner | None = None,
        event_writer: EventWriter | None = None,
        transition_repository: TransitionRepository | None = None,
        guard_repository: GuardRepository | None = None,
        idempotency_service: IdempotencyService | None = None,
    ) -> None:
        from src.kernel.guards import GuardRegistry

        self.root = root
        self.transitions = transition_registry or TransitionRegistry.from_repository(root)
        self.authorizer = authorizer or TransitionAuthorizer()
        self.guard_runner = guard_runner or GuardRunner(GuardRegistry.from_repository(root))
        self.events = event_writer or EventWriter(root)
        self.transition_repository = transition_repository or TransitionRepository()
        self.guard_repository = guard_repository or GuardRepository()
        self.idempotency = idempotency_service or IdempotencyService()
        self.state_adapters = state_adapters

    def execute(self, cursor, request: TransitionRequest) -> TransitionResult:
        request_hash = sha256_canonical(request.semantic_payload())
        decision = self.idempotency.check(cursor, request.service_name, request.idempotency_key, request_hash)
        if decision.status == 'REPLAY':
            return TransitionResult.from_payload(decision.prior.result_payload, replayed=True)

        try:
            transition = self.transitions.get(request.transition_id)
        except TransitionRegistryError:
            result = TransitionResult(
                status='REJECTED',
                transition_id=request.transition_id,
                entity_id=request.entity_id,
                reason_code='TRANSITION_NOT_ALLOWED',
            )
            self._record_processed_command(cursor, request, request_hash, result)
            return result

        try:
            command_event = self.events.write(cursor, EventDraft(
                event_type='COMMAND_ACCEPTED',
                source_system='KERNEL',
                actor_type=request.actor_type,
                actor_id=request.actor_id,
                correlation_id=request.correlation_id,
                causation_event_id=request.causation_event_id,
                reason_code=transition.reason_code,
                payload={
                    'command_type': request.command_type,
                    'transition_id': transition.transition_id,
                    'entity_type': transition.entity_type,
                    'entity_id': str(request.entity_id),
                    'state_dimension': transition.state_dimension,
                },
            ))
        except Exception as exc:
            raise TransitionEngineInfrastructureError('command audit persistence failed; rollback required') from exc

        try:
            self.authorizer.authorize(transition, request.caller_id)
        except TransitionAuthorizationError:
            return self._record_unauthorized(cursor, request, request_hash, transition, command_event.event_id)

        adapter = self.state_adapters.get(transition.entity_type, transition.state_dimension)
        current = adapter.lock_current_state(cursor, request.entity_id)

        context = GuardContext(
            entity_id=request.entity_id,
            entity_type=transition.entity_type,
            state_dimension=transition.state_dimension,
            expected_state=transition.from_state,
            actual_state=current.state if current else None,
            caller_id=request.caller_id,
            allowed_callers=transition.allowed_callers,
            entity_exists=current is not None,
            metadata=request.metadata,
        )
        guard_results = self.guard_runner.run(transition.required_guards, context)
        overall = self.guard_runner.overall_result(guard_results)

        if overall != 'PASS':
            status = 'BLOCKED' if overall in {'BLOCK', 'ERROR'} else 'REJECTED'
            reason = next(
                (g.reason_code for g in guard_results if g.result in {'FAIL', 'BLOCK', 'ERROR'} and g.reason_code),
                'GUARD_REJECTED',
            )
            return self._record_guard_rejection(
                cursor, request, request_hash, transition, current, guard_results, status, reason, command_event.event_id
            )

        assert current is not None  # ENTITY_EXISTS is mandatory for the kernel transition.
        try:
            updated = adapter.apply_state(
                cursor,
                request.entity_id,
                transition.from_state,
                transition.to_state,
                current.state_version,
            )
        except (EntityNotFoundError, StateConflictError):
            return self._record_conflict(cursor, request, request_hash, transition, current, guard_results, command_event.event_id)

        try:
            event = self.events.write(
                cursor,
                EventDraft(
                    event_type=transition.emitted_events[0] if transition.emitted_events else 'TRANSITION_APPLIED',
                    source_system='KERNEL',
                    actor_type=request.actor_type,
                    actor_id=request.actor_id,
                    correlation_id=request.correlation_id,
                    causation_event_id=command_event.event_id,
                    reason_code=transition.reason_code,
                    payload={
                        'transition_id': transition.transition_id,
                        'entity_type': transition.entity_type,
                        'entity_id': str(request.entity_id),
                        'state_dimension': transition.state_dimension,
                        'from_state': transition.from_state,
                        'to_state': transition.to_state,
                        'state_version': updated.state_version,
                    },
                ),
            )
            transition_record_id = uuid4()
            self.transition_repository.insert(cursor, StateTransitionRecord(
                transition_record_id=transition_record_id,
                transition_id=transition.transition_id,
                entity_type=transition.entity_type,
                entity_id=request.entity_id,
                state_dimension=transition.state_dimension,
                from_state=transition.from_state,
                to_state=transition.to_state,
                result='APPLIED',
                reason_code=transition.reason_code,
                event_id=event.event_id,
                correlation_id=request.correlation_id,
                actor_type=request.actor_type,
                actor_id=request.actor_id,
            ))
            self._record_guards(cursor, transition_record_id, request.correlation_id, guard_results)
            result = TransitionResult(
                status='APPLIED',
                transition_id=transition.transition_id,
                entity_id=request.entity_id,
                from_state=transition.from_state,
                to_state=transition.to_state,
                state_version=updated.state_version,
                reason_code=transition.reason_code,
                event_id=event.event_id,
            )
            self._record_processed_command(cursor, request, request_hash, result)
            return result
        except Exception as exc:
            raise TransitionEngineInfrastructureError('transition persistence failed; rollback required') from exc

    def _record_unauthorized(self, cursor, request, request_hash, transition, command_event_id) -> TransitionResult:
        event = self.events.write(cursor, EventDraft(
            event_type='UNAUTHORIZED_TRANSITION_ATTEMPT',
            source_system='KERNEL',
            actor_type=request.actor_type,
            actor_id=request.actor_id,
            correlation_id=request.correlation_id,
            causation_event_id=command_event_id,
            reason_code='CALLER_NOT_AUTHORIZED',
            payload={
                'transition_id': transition.transition_id,
                'entity_type': transition.entity_type,
                'entity_id': str(request.entity_id),
                'state_dimension': transition.state_dimension,
            },
        ))
        record_id = uuid4()
        self.transition_repository.insert(cursor, StateTransitionRecord(
            transition_record_id=record_id,
            transition_id=transition.transition_id,
            entity_type=transition.entity_type,
            entity_id=request.entity_id,
            state_dimension=transition.state_dimension,
            from_state=transition.from_state,
            to_state=transition.to_state,
            result='REJECTED',
            reason_code='CALLER_NOT_AUTHORIZED',
            event_id=event.event_id,
            correlation_id=request.correlation_id,
            actor_type=request.actor_type,
            actor_id=request.actor_id,
        ))
        result = TransitionResult(
            status='REJECTED', transition_id=transition.transition_id, entity_id=request.entity_id,
            from_state=transition.from_state, to_state=transition.to_state,
            reason_code='CALLER_NOT_AUTHORIZED', event_id=event.event_id,
        )
        self._record_processed_command(cursor, request, request_hash, result)
        return result

    def _record_guard_rejection(self, cursor, request, request_hash, transition, current, guard_results, status, reason, command_event_id):
        event = self.events.write(cursor, EventDraft(
            event_type=transition.rejection_event or 'TRANSITION_REJECTED',
            source_system='KERNEL', actor_type=request.actor_type, actor_id=request.actor_id,
            correlation_id=request.correlation_id, causation_event_id=command_event_id,
            reason_code='GUARD_REJECTED',
            payload={
                'transition_id': transition.transition_id,
                'entity_type': transition.entity_type,
                'entity_id': str(request.entity_id),
                'state_dimension': transition.state_dimension,
                'from_state': transition.from_state,
                'to_state': transition.to_state,
                'guard_result': status,
                'guard_reason_code': reason,
            },
        ))
        record_id = uuid4()
        self.transition_repository.insert(cursor, StateTransitionRecord(
            transition_record_id=record_id, transition_id=transition.transition_id,
            entity_type=transition.entity_type, entity_id=request.entity_id,
            state_dimension=transition.state_dimension, from_state=transition.from_state,
            to_state=transition.to_state, result=status, reason_code='GUARD_REJECTED',
            event_id=event.event_id, correlation_id=request.correlation_id,
            actor_type=request.actor_type, actor_id=request.actor_id,
        ))
        self._record_guards(cursor, record_id, request.correlation_id, guard_results)
        first_failed = next((g for g in guard_results if g.result in {'FAIL','BLOCK','ERROR'}), None)
        if first_failed:
            self.events.write(cursor, EventDraft(
                event_type='GUARD_FAILED', source_system='KERNEL', actor_type=request.actor_type,
                actor_id=request.actor_id, correlation_id=request.correlation_id,
                causation_event_id=event.event_id, reason_code='GUARD_REJECTED',
                payload={'transition_id': transition.transition_id, 'guard_id': first_failed.guard_id,
                         'guard_result': first_failed.result, 'guard_reason_code': first_failed.reason_code},
            ))
        result = TransitionResult(
            status=status, transition_id=transition.transition_id, entity_id=request.entity_id,
            from_state=current.state if current else None, to_state=transition.to_state,
            state_version=current.state_version if current else None,
            reason_code=reason, event_id=event.event_id,
        )
        self._record_processed_command(cursor, request, request_hash, result)
        return result

    def _record_conflict(self, cursor, request, request_hash, transition, current, guard_results, command_event_id):
        event = self.events.write(cursor, EventDraft(
            event_type=transition.rejection_event or 'TRANSITION_REJECTED', source_system='KERNEL',
            actor_type=request.actor_type, actor_id=request.actor_id, correlation_id=request.correlation_id,
            causation_event_id=command_event_id, reason_code='TRANSITION_CONFLICT',
            payload={'transition_id': transition.transition_id, 'entity_type': transition.entity_type,
                     'entity_id': str(request.entity_id), 'state_dimension': transition.state_dimension,
                     'from_state': transition.from_state, 'to_state': transition.to_state},
        ))
        record_id = uuid4()
        self.transition_repository.insert(cursor, StateTransitionRecord(
            transition_record_id=record_id, transition_id=transition.transition_id,
            entity_type=transition.entity_type, entity_id=request.entity_id,
            state_dimension=transition.state_dimension, from_state=transition.from_state,
            to_state=transition.to_state, result='CONFLICT', reason_code='TRANSITION_CONFLICT',
            event_id=event.event_id, correlation_id=request.correlation_id,
            actor_type=request.actor_type, actor_id=request.actor_id,
        ))
        self._record_guards(cursor, record_id, request.correlation_id, guard_results)
        result = TransitionResult(
            status='CONFLICT', transition_id=transition.transition_id, entity_id=request.entity_id,
            from_state=current.state if current else None, to_state=transition.to_state,
            state_version=current.state_version if current else None,
            reason_code='TRANSITION_CONFLICT', event_id=event.event_id,
        )
        self._record_processed_command(cursor, request, request_hash, result)
        return result

    def _record_guards(self, cursor, transition_record_id, correlation_id, guard_results):
        for ordinal, guard in enumerate(guard_results):
            self.guard_repository.insert(cursor, GuardEvaluationRecord(
                guard_evaluation_id=uuid4(), transition_record_id=transition_record_id,
                guard_id=guard.guard_id, ordinal=ordinal, result=guard.result,
                reason_code=guard.reason_code, safe_details=dict(guard.safe_details),
                correlation_id=correlation_id,
            ))

    def _record_processed_command(self, cursor, request, request_hash, result):
        self.idempotency.record(cursor, ProcessedCommand(
            command_id=uuid4(), service_name=request.service_name, command_type=request.command_type,
            idempotency_key=request.idempotency_key, request_hash=request_hash,
            result_status=result.status, result_payload=result.to_payload(), correlation_id=request.correlation_id,
        ))
