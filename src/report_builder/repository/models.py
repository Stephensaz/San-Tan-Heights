from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

@dataclass(frozen=True)
class ReportVersion:
    report_id: UUID
    property_id: UUID
    report_variant: str
    version_number: int
    snapshot_id: UUID
    report_schema_version: str
    content_contract_version: str
    variant_policy_version: str
    builder_version: str
    report_input_hash: str
    canonical_payload_hash: str
    canonical_payload: dict[str, Any]
    dependency_manifest_hash: str
    generation_reason: str
    content_state: str = 'BUILDING'
    health_state: str = 'CLEAN'
    qa_status: str = 'PENDING'
    qa_completed_at: datetime | None = None
    publication_eligible: bool = False
    stored_payload_hash: str | None = None
    supersedes_report_id: UUID | None = None
    superseded_by_report_id: UUID | None = None
    created_at: datetime | None = None
    created_by: str = 'REPORT_BUILDER'

@dataclass(frozen=True)
class ReportDependency:
    report_dependency_id: UUID
    report_id: UUID
    dependency_type: str
    dependency_id: str
    semantic_fingerprint: str
    dependency_version: str
    source_snapshot_id: UUID | None
