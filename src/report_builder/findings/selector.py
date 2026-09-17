from __future__ import annotations
from dataclasses import dataclass
from typing import Iterable

from src.report_builder.sections.registry import ReportSectionRegistry
from src.report_builder.variant.registry import VariantPolicyRegistry
from src.snapshot.repository.models import SnapshotFindingRecord


class FindingSelectionError(ValueError):
    pass


@dataclass(frozen=True)
class FindingSelection:
    finding: SnapshotFindingRecord
    section_id: str
    classification: str


_SCOPE_CLASSIFICATION = {
    "PUBLIC": "PUBLIC_DATA",
    "ALL": "PUBLIC_DATA",
    "SELLER": "SELLER_DATA",
    "AGENT_SELLER": "SELLER_DATA",
    "AGENT": "AGENT_INTERNAL",
    "NONE": "RESTRICTED",
}


class FindingSelector:
    """Selects governed snapshot findings for a report variant without deriving new facts."""

    def __init__(self, variants: VariantPolicyRegistry, sections: ReportSectionRegistry):
        self.variants = variants
        self.sections = sections

    def _section_for(self, finding_type: str, variant: str) -> str | None:
        matches = [
            section.section_id
            for section in self.sections.for_variant(variant)
            if finding_type in section.finding_types
        ]
        # A finding type may support more than one section (for example builder/floor-plan
        # identity can support both identity and home DNA). Selection assigns one canonical
        # primary section using the governed section order; later card assembly may reference
        # the same selected finding where explicitly permitted without duplicating the finding.
        return matches[0] if matches else None

    def select(self, findings: Iterable[SnapshotFindingRecord], variant: str) -> tuple[FindingSelection, ...]:
        policy = self.variants.get(variant)
        selected: list[FindingSelection] = []
        seen: set[str] = set()

        for finding in findings:
            if finding.finding_id in seen:
                raise FindingSelectionError(f"duplicate finding_id: {finding.finding_id}")
            seen.add(finding.finding_id)

            if finding.production_status != "PRODUCTION_READY" or finding.qa_status != "PASS":
                continue
            if finding.finding_type in policy.prohibited_finding_types:
                continue
            if not policy.allows_publication_scope(finding.publication_scope):
                continue

            try:
                classification = _SCOPE_CLASSIFICATION[finding.publication_scope]
            except KeyError as exc:
                raise FindingSelectionError(
                    f"unknown publication scope: {finding.publication_scope}"
                ) from exc
            if not policy.allows_classification(classification):
                continue

            section_id = self._section_for(finding.finding_type, variant)
            if section_id is None:
                # A production finding may be governed but not consumed by this report contract.
                continue
            selected.append(FindingSelection(finding, section_id, classification))

        return tuple(sorted(selected, key=lambda x: (self.sections.get(x.section_id).order, x.finding.finding_type, x.finding.finding_id)))
