from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

@dataclass(frozen=True)
class CurrentReportPointer:
    property_id: UUID
    report_variant: str
    report_id: UUID
    pointer_version: int = 1
    updated_at: datetime | None = None
    updated_by: str = 'PUBLICATION_SERVICE'

@dataclass(frozen=True)
class ChannelPointer:
    property_id: UUID
    report_variant: str
    channel: str
    report_id: UUID
    render_id: UUID
    pointer_version: int = 1
    updated_at: datetime | None = None
    updated_by: str = 'PUBLICATION_SERVICE'

@dataclass(frozen=True)
class PublicationHistoryRecord:
    property_id: UUID
    report_variant: str
    report_id: UUID
    action: str
    actor: str
    channel: str | None = None
    render_id: UUID | None = None
    reason_code: str | None = None
    correlation_id: UUID | None = None
