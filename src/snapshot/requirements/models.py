from __future__ import annotations
from dataclasses import dataclass
from typing import Any

@dataclass(frozen=True)
class SnapshotRequirement:
    requirement_id: str
    scope: str
    required: bool
    satisfied_by: dict[str, Any]
    failure_action: str
    failure_reason_code: str

@dataclass(frozen=True)
class RequirementResult:
    requirement_id: str
    requirement_scope: str
    required_flag: bool
    status: str
    finding_id: str | None = None
    dependency_type: str | None = None
    dependency_id: str | None = None
    reason_code: str | None = None

@dataclass(frozen=True)
class RequirementEvaluation:
    results: tuple[RequirementResult, ...]
    completeness_status: str
