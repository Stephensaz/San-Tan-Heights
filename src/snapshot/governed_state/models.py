from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from uuid import UUID

@dataclass(frozen=True)
class GovernedFinding:
    finding_id: str
    finding_type: str
    passport_id: str
    passport_version: str
    canonical_value: Any
    confidence_code: str
    qa_status: str
    production_status: str
    publication_scope: str
    approved_wording: dict[str, str | None]
    wording_versions: dict[str, str | None]
    semantic_fingerprint: str
    evidence_reference_set_hash: str

@dataclass(frozen=True)
class GovernedDependency:
    dependency_type: str
    dependency_id: str
    semantic_fingerprint: str
    record_fingerprint: str
    dependency_version: str
    required: bool
    variant_scope: tuple[str, ...]

@dataclass(frozen=True)
class GovernedPropertyState:
    property_id: UUID
    governed_state_version: str
    source_read_token: str
    intelligence_schema_version: str
    governance_schema_version: str
    model_version: str
    property_identity_status: str
    qa_status: str
    findings: tuple[GovernedFinding, ...]
    dependencies: tuple[GovernedDependency, ...]
