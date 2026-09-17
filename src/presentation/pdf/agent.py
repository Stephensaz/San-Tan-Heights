from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256

from src.presentation.agent import AgentReportView
from src.presentation.pdf.foundation import PdfTemplateFoundation, PdfTemplatePlan
from src.shared.canonical_json import canonical_json


@dataclass(frozen=True)
class AgentPdfFinding:
    finding_id: str
    finding_type: str
    label: str
    display_text: str
    status_label: str | None
    confidence_label: str | None
    limitation: str | None
    source_snapshot_id: str
    semantic_fingerprint: str


@dataclass(frozen=True)
class AgentPdfCard:
    card_id: str
    card_type: str
    title: str
    body: str | None
    status_label: str | None
    findings: tuple[AgentPdfFinding, ...]


@dataclass(frozen=True)
class AgentPdfSection:
    section_id: str
    title: str
    summary: str | None
    cards: tuple[AgentPdfCard, ...]


@dataclass(frozen=True)
class AgentPdfDocument:
    property_id: str
    address: str
    community: str
    phase: str | None
    builder: str | None
    floor_plan: str | None
    verified_through: str
    market_data_through: str | None
    builder_data_through: str | None
    summary: tuple[str, ...]
    sections: tuple[AgentPdfSection, ...]
    disclaimers: tuple[str, ...]
    snapshot_id: str
    dependency_manifest_hash: str
    template: PdfTemplatePlan

    def canonical_payload(self) -> dict[str, object]:
        return {
            "property_id": self.property_id,
            "address": self.address,
            "community": self.community,
            "phase": self.phase,
            "builder": self.builder,
            "floor_plan": self.floor_plan,
            "verified_through": self.verified_through,
            "market_data_through": self.market_data_through,
            "builder_data_through": self.builder_data_through,
            "summary": list(self.summary),
            "sections": [
                {
                    "section_id": section.section_id,
                    "title": section.title,
                    "summary": section.summary,
                    "cards": [
                        {
                            "card_id": card.card_id,
                            "card_type": card.card_type,
                            "title": card.title,
                            "body": card.body,
                            "status_label": card.status_label,
                            "findings": [finding.__dict__ for finding in card.findings],
                        }
                        for card in section.cards
                    ],
                }
                for section in self.sections
            ],
            "disclaimers": list(self.disclaimers),
            "snapshot_id": self.snapshot_id,
            "dependency_manifest_hash": self.dependency_manifest_hash,
            "template": self.template.canonical_payload(),
        }

    @property
    def fingerprint(self) -> str:
        return sha256(canonical_json(self.canonical_payload()).encode("utf-8")).hexdigest()


class AgentPdfComposer:
    """Compose an Agent-only PDF document model from the governed Agent view."""

    def __init__(self, foundation: PdfTemplateFoundation) -> None:
        self.foundation = foundation

    def compose(self, report: AgentReportView) -> AgentPdfDocument:
        if not isinstance(report, AgentReportView):
            raise ValueError("AgentPdfComposer requires an AgentReportView")

        sections = tuple(
            AgentPdfSection(
                section_id=section.section_id,
                title=section.title,
                summary=section.summary,
                cards=tuple(
                    AgentPdfCard(
                        card_id=card.card_id,
                        card_type=card.card_type,
                        title=card.title,
                        body=card.body,
                        status_label=card.status_label,
                        findings=tuple(
                            AgentPdfFinding(
                                finding_id=finding.finding_id,
                                finding_type=finding.finding_type,
                                label=finding.label,
                                display_text=finding.display_text,
                                status_label=finding.status_label,
                                confidence_label=finding.confidence_label,
                                limitation=finding.limitation,
                                source_snapshot_id=finding.source_snapshot_id,
                                semantic_fingerprint=finding.semantic_fingerprint,
                            )
                            for finding in card.findings
                        ),
                    )
                    for card in section.cards
                ),
            )
            for section in report.sections
        )
        template = self.foundation.plan(section.section_id for section in sections)
        return AgentPdfDocument(
            property_id=report.property_id,
            address=report.address,
            community=report.community,
            phase=report.phase,
            builder=report.builder,
            floor_plan=report.floor_plan,
            verified_through=report.verified_through,
            market_data_through=report.market_data_through,
            builder_data_through=report.builder_data_through,
            summary=report.summary,
            sections=sections,
            disclaimers=report.disclaimers,
            snapshot_id=report.snapshot_id,
            dependency_manifest_hash=report.dependency_manifest_hash,
            template=template,
        )
