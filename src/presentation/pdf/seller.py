from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256

from src.presentation.pdf.foundation import PdfTemplateFoundation, PdfTemplatePlan
from src.presentation.seller import SellerReportView
from src.shared.canonical_json import canonical_json


@dataclass(frozen=True)
class SellerPdfFinding:
    finding_id: str
    finding_type: str
    label: str
    display_text: str
    status_label: str | None
    confidence_label: str | None
    limitation: str | None


@dataclass(frozen=True)
class SellerPdfCard:
    card_id: str
    card_type: str
    title: str
    body: str | None
    status_label: str | None
    findings: tuple[SellerPdfFinding, ...]


@dataclass(frozen=True)
class SellerPdfSection:
    section_id: str
    title: str
    summary: str | None
    cards: tuple[SellerPdfCard, ...]


@dataclass(frozen=True)
class SellerPdfDocument:
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
    sections: tuple[SellerPdfSection, ...]
    disclaimers: tuple[str, ...]
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
            "template": self.template.canonical_payload(),
        }

    @property
    def fingerprint(self) -> str:
        return sha256(canonical_json(self.canonical_payload()).encode("utf-8")).hexdigest()


class SellerPdfComposer:
    """Compose a Seller-safe PDF document model from the governed Seller view."""

    def __init__(self, foundation: PdfTemplateFoundation) -> None:
        self.foundation = foundation

    def compose(self, report: SellerReportView) -> SellerPdfDocument:
        if not isinstance(report, SellerReportView):
            raise ValueError("SellerPdfComposer requires a SellerReportView")

        sections = tuple(
            SellerPdfSection(
                section_id=section.section_id,
                title=section.title,
                summary=section.summary,
                cards=tuple(
                    SellerPdfCard(
                        card_id=card.card_id,
                        card_type=card.card_type,
                        title=card.title,
                        body=card.body,
                        status_label=card.status_label,
                        findings=tuple(
                            SellerPdfFinding(
                                finding_id=finding.finding_id,
                                finding_type=finding.finding_type,
                                label=finding.label,
                                display_text=finding.display_text,
                                status_label=finding.status_label,
                                confidence_label=finding.confidence_label,
                                limitation=finding.limitation,
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
        return SellerPdfDocument(
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
            template=template,
        )
