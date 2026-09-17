from __future__ import annotations
from dataclasses import dataclass
from uuid import UUID
from src.publication.repository import PublicationHistoryRecord

@dataclass(frozen=True)
class SupersessionResult:
    superseded_report_id: UUID | None = None
    superseded_render_id: UUID | None = None

class PublicationHistoryService:
    """Append-only lifecycle evidence. Never mutates historical report/render rows."""
    def __init__(self, repository): self.repository = repository

    def record_pointer_replacement(self, cursor, *, property_id, report_variant, channel,
                                   previous_report_id, previous_render_id,
                                   new_report_id, new_render_id, actor,
                                   reason_code=None, correlation_id=None):
        if previous_render_id is not None and previous_render_id != new_render_id:
            self.repository.append_history(cursor, PublicationHistoryRecord(
                property_id, report_variant, previous_report_id or new_report_id,
                'SUPERSEDED', actor, channel, previous_render_id, reason_code, correlation_id))
        if previous_report_id is not None and previous_report_id != new_report_id:
            self.repository.append_history(cursor, PublicationHistoryRecord(
                property_id, report_variant, previous_report_id,
                'SEMANTIC_SUPERSEDED', actor, None, None, reason_code, correlation_id))
        return SupersessionResult(previous_report_id, previous_render_id)
