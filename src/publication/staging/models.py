from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

@dataclass(frozen=True)
class PublicationStage:
    staging_id: UUID
    property_id: UUID
    report_variant: str
    channel: str
    report_id: UUID
    render_id: UUID
    staging_state: str = 'STAGED'
    requested_by: str = 'PUBLICATION_SERVICE'
    reason_code: str | None = None
    correlation_id: UUID | None = None
    created_at: datetime | None = None
