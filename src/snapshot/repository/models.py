from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

@dataclass(frozen=True)
class SnapshotRecord:
    snapshot_id: UUID; property_id: UUID; snapshot_sequence: int; snapshot_reason: str
    governed_state_version: str; source_read_token: str; intelligence_schema_version: str; governance_schema_version: str; model_version: str
    semantic_fingerprint: str; agent_semantic_fingerprint: str; seller_semantic_fingerprint: str; public_semantic_fingerprint: str; snapshot_hash: str
    snapshot_completeness_status: str; qa_status: str; created_by: str
    qa_completed_at: datetime | None = None; supersedes_snapshot_id: UUID | None = None

@dataclass(frozen=True)
class SnapshotFindingRecord:
    snapshot_finding_id: UUID; snapshot_id: UUID; finding_id: str; finding_type: str; passport_id: str; passport_version: str; passport_semantic_fingerprint: str
    canonical_value: Any; confidence_code: str; qa_status: str; production_status: str; publication_scope: str
    agent_wording: str|None; seller_wording: str|None; public_wording: str|None
    agent_wording_version: str|None; seller_wording_version: str|None; public_wording_version: str|None
    semantic_fingerprint: str; evidence_reference_set_hash: str

@dataclass(frozen=True)
class SnapshotDependencyRecord:
    snapshot_dependency_id: UUID; snapshot_id: UUID; dependency_type: str; dependency_id: str; record_fingerprint: str; semantic_fingerprint: str; dependency_version: str
    required: bool; affects_agent: bool; affects_seller: bool; affects_public: bool

@dataclass(frozen=True)
class SnapshotRequirementResultRecord:
    snapshot_requirement_result_id: UUID; snapshot_id: UUID; requirement_id: str; requirement_scope: str; required_flag: bool; status: str
    finding_id: str|None=None; dependency_type: str|None=None; dependency_id: str|None=None; reason_code: str|None=None

@dataclass(frozen=True)
class SnapshotDiffRecord:
    snapshot_diff_id: UUID; old_snapshot_id: UUID; new_snapshot_id: UUID; diff_payload: dict[str,Any]; diff_hash: str
