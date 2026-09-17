from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from typing import Any

from src.presentation.agent import AgentReportView
from src.presentation.audience import AudiencePresentationPolicies
from src.presentation.package import PresentationAudience
from src.presentation.public import PublicReportView
from src.presentation.seller import SellerReportView
from src.shared.canonical_json import canonical_json


@dataclass(frozen=True)
class EvidenceDisclosureItem:
    finding_id: str
    label: str
    status_label: str | None
    confidence_label: str | None
    limitation: str | None
    source_snapshot_id: str | None = None
    semantic_fingerprint: str | None = None

    def canonical_payload(self) -> dict[str, object]:
        return {
            "finding_id": self.finding_id,
            "label": self.label,
            "status_label": self.status_label,
            "confidence_label": self.confidence_label,
            "limitation": self.limitation,
            "source_snapshot_id": self.source_snapshot_id,
            "semantic_fingerprint": self.semantic_fingerprint,
        }


@dataclass(frozen=True)
class EvidenceDisclosureSet:
    audience: str
    evidence_depth: str
    items: tuple[EvidenceDisclosureItem, ...]
    disclaimers: tuple[str, ...]

    def canonical_payload(self) -> dict[str, object]:
        return {
            "audience": self.audience,
            "evidence_depth": self.evidence_depth,
            "items": [item.canonical_payload() for item in self.items],
            "disclaimers": list(self.disclaimers),
        }

    @property
    def fingerprint(self) -> str:
        return sha256(canonical_json(self.canonical_payload()).encode("utf-8")).hexdigest()


class EvidenceDisclosureBuilder:
    """Build audience-safe disclosure components from governed report views only.

    This layer does not query raw findings, recover hidden lineage, infer sources,
    or broaden evidence visibility. It projects only fields already present in
    the audience-specific report view produced upstream.
    """

    def __init__(self, policies: AudiencePresentationPolicies) -> None:
        self.policies = policies

    def build(
        self,
        report: AgentReportView | SellerReportView | PublicReportView,
        *,
        audience: PresentationAudience,
    ) -> EvidenceDisclosureSet:
        self._require_matching_view(report, audience)
        policy = self.policies.for_audience(audience)

        items: list[EvidenceDisclosureItem] = []
        for section in report.sections:
            for card in section.cards:
                for finding in card.findings:
                    if audience is PresentationAudience.AGENT:
                        source_snapshot_id = self._required_text(
                            getattr(finding, "source_snapshot_id", None),
                            "Agent evidence requires source_snapshot_id",
                        )
                        semantic_fingerprint = self._required_text(
                            getattr(finding, "semantic_fingerprint", None),
                            "Agent evidence requires semantic_fingerprint",
                        )
                    else:
                        if hasattr(finding, "source_snapshot_id") or hasattr(finding, "semantic_fingerprint"):
                            raise ValueError(f"{audience.value} evidence view must not expose Agent lineage")
                        source_snapshot_id = None
                        semantic_fingerprint = None

                    items.append(
                        EvidenceDisclosureItem(
                            finding_id=self._required_text(finding.finding_id, "evidence finding_id is required"),
                            label=self._required_text(finding.label, "evidence label is required"),
                            status_label=finding.status_label,
                            confidence_label=finding.confidence_label,
                            limitation=finding.limitation,
                            source_snapshot_id=source_snapshot_id,
                            semantic_fingerprint=semantic_fingerprint,
                        )
                    )

        return EvidenceDisclosureSet(
            audience=audience.value,
            evidence_depth=policy.evidence_depth,
            items=tuple(items),
            disclaimers=tuple(report.disclaimers),
        )

    @staticmethod
    def _require_matching_view(
        report: AgentReportView | SellerReportView | PublicReportView,
        audience: PresentationAudience,
    ) -> None:
        expected: dict[PresentationAudience, type[Any]] = {
            PresentationAudience.AGENT: AgentReportView,
            PresentationAudience.SELLER: SellerReportView,
            PresentationAudience.PUBLIC: PublicReportView,
        }
        if not isinstance(report, expected[audience]):
            raise ValueError(f"evidence disclosure view does not match audience {audience.value}")

    @staticmethod
    def _required_text(value: object, message: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError(message)
        return value
