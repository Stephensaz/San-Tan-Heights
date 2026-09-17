from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID


@dataclass(frozen=True)
class ReleaseRecord:
    release_id: UUID
    release_state: str = 'DRAFT'
    release_name: str | None = None
    release_scope: dict[str, Any] = field(default_factory=dict)
    policy_version: str | None = None
    membership_fingerprint: str | None = None
    manifest_fingerprint: str | None = None
    total_item_count: int = 0
    correlation_id: UUID | None = None
    reason_code: str | None = None
    created_by: str = 'RELEASE_SERVICE'
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass(frozen=True)
class ReleaseManifestRecord:
    release_id: UUID
    membership_fingerprint: str
    manifest_fingerprint: str
    manifest_payload: dict[str, Any]
    frozen_by: str = 'RELEASE_SERVICE'
    frozen_at: datetime | None = None


@dataclass(frozen=True)
class ReleaseItemRecord:
    release_item_id: UUID
    release_id: UUID
    property_id: UUID
    report_variant: str
    membership_ordinal: int
    channel: str | None = None
    item_state: str = 'PENDING'
    target_snapshot_id: UUID | None = None
    target_report_id: UUID | None = None
    target_render_id: UUID | None = None
    target_semantic_fingerprint: str | None = None
    target_presentation_fingerprint: str | None = None
    last_error_code: str | None = None
