from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Mapping

GUARD_RESULTS = frozenset({'PASS','FAIL','BLOCK','ERROR','NOT_EVALUATED'})

@dataclass(frozen=True)
class GuardDefinition:
    guard_id: str
    implementation: str
    read_only: bool = True

@dataclass(frozen=True)
class GuardContext:
    entity_id: object
    entity_type: str
    state_dimension: str
    expected_state: str
    actual_state: str | None
    caller_id: str
    allowed_callers: frozenset[str] = frozenset()
    entity_exists: bool = True
    metadata: Mapping[str, Any] = field(default_factory=dict)

@dataclass(frozen=True)
class GuardResult:
    guard_id: str
    result: str
    reason_code: str | None = None
    safe_details: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.result not in GUARD_RESULTS:
            raise ValueError(f'unsupported guard result: {self.result}')
