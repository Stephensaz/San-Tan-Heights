from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class TransitionDefinition:
    transition_id: str
    entity_type: str
    state_dimension: str
    from_state: str
    to_state: str
    allowed_callers: frozenset[str]
    required_guards: tuple[str, ...]
    emitted_events: tuple[str, ...]
    rejection_event: str | None
    reason_code: str | None
