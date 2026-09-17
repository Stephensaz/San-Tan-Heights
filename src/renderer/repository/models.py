from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class RenderVersion:
    render_id: UUID
    report_id: UUID
    render_type: str
    render_version: int
    render_contract_version: str
    template_id: str
    template_version: str
    renderer_version: str
    presentation_input_hash: str
    artifact_hash: str | None = None
    artifact_size_bytes: int | None = None
    storage_uri: str | None = None
    mime_type: str | None = None
    content_state: str = 'BUILDING'
    health_state: str = 'CLEAN'
    qa_status: str = 'PENDING'
    qa_completed_at: datetime | None = None
    publication_eligible: bool = False
    supersedes_render_id: UUID | None = None
    superseded_by_render_id: UUID | None = None
    created_at: datetime | None = None
    created_by: str = 'RENDERER'


@dataclass(frozen=True)
class RenderDependency:
    render_dependency_id: UUID
    render_id: UUID
    dependency_type: str
    dependency_id: str
    semantic_fingerprint: str
    dependency_version: str
    slot_id: str | None = None
