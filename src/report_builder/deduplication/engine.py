from __future__ import annotations
from dataclasses import dataclass
from uuid import UUID

from src.report_builder.repository import ReportRepository


@dataclass(frozen=True)
class ReportDeduplicationResult:
    reused: bool
    existing_report_id: UUID | None
    reason: str


class ReportDeduplicationEngine:
    """Semantic deduplication is keyed by report_input_hash, not snapshot or render identity."""

    def __init__(self, repository: ReportRepository | None = None):
        self.repository = repository or ReportRepository()

    def find(self, cursor, *, property_id: UUID, report_variant: str, report_input_hash: str) -> ReportDeduplicationResult:
        existing = self.repository.find_equivalent(cursor, property_id, report_variant, report_input_hash)
        if existing is not None:
            return ReportDeduplicationResult(True, existing, 'SEMANTICALLY_EQUIVALENT_REPORT_EXISTS')
        return ReportDeduplicationResult(False, None, 'NO_EQUIVALENT_REPORT')
