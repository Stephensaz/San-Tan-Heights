from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Iterable
from uuid import UUID

from src.report_builder.dependencies import ReportDependencyManifest
from src.report_builder.findings.selector import FindingSelection
from src.report_builder.glossary.resolver import GlossaryEntry
from src.report_builder.labels.resolver import FriendlyLabelRegistry
from src.report_builder.schema import CanonicalReportSchema
from src.report_builder.sections.registry import ReportSectionRegistry
from src.report_builder.wording.resolver import ResolvedWording


class CanonicalPayloadBuildError(ValueError):
    pass


@dataclass(frozen=True)
class CanonicalPayloadInputs:
    property_id: UUID
    snapshot_id: UUID
    report_variant: str
    report_schema_version: str
    content_contract_version: str
    variant_policy_version: str
    verified_through: datetime
    property_identity: dict[str, Any]
    summary_items: tuple[str, ...]
    section_titles: dict[str, str]
    disclaimers: tuple[str, ...]
    brand_profile_id: str
    brand_version: str
    market_data_through: datetime | None = None
    builder_data_through: datetime | None = None
    media_slots: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    diagram_slots: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    evidence_disclosures: tuple[dict[str, Any], ...] = field(default_factory=tuple)


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    text = value.isoformat()
    return text.replace("+00:00", "Z")


class CanonicalPayloadBuilder:
    """Assembles governed display-ready content. It never derives new property intelligence."""

    def __init__(
        self,
        *,
        sections: ReportSectionRegistry,
        labels: FriendlyLabelRegistry,
        schema: CanonicalReportSchema,
    ):
        self.sections = sections
        self.labels = labels
        self.schema = schema

    def build(
        self,
        *,
        inputs: CanonicalPayloadInputs,
        selections: Iterable[FindingSelection],
        resolved_wording: dict[str, ResolvedWording],
        glossary: Iterable[GlossaryEntry],
        dependency_manifest: ReportDependencyManifest,
    ) -> dict[str, Any]:
        selections = tuple(selections)
        if not inputs.summary_items:
            raise CanonicalPayloadBuildError("summary_items must be supplied as governed content")
        if not inputs.disclaimers:
            raise CanonicalPayloadBuildError("at least one approved disclaimer is required")

        findings: list[dict[str, Any]] = []
        cards: list[dict[str, Any]] = []
        finding_ids_by_section: dict[str, list[str]] = {}
        for selection in selections:
            finding = selection.finding
            wording = resolved_wording.get(finding.finding_id)
            if wording is None:
                raise CanonicalPayloadBuildError(f"missing resolved wording: {finding.finding_id}")
            label = self.labels.resolve(finding.finding_type, inputs.report_variant)
            findings.append({
                "finding_id": finding.finding_id,
                "finding_type": finding.finding_type,
                "label": label,
                "display_text": wording.text,
                "section_id": selection.section_id,
                "status_label": None,
                "confidence_label": None,
                "limitation": None,
                "source_snapshot_id": str(inputs.snapshot_id),
                "semantic_fingerprint": finding.semantic_fingerprint,
            })
            finding_ids_by_section.setdefault(selection.section_id, []).append(finding.finding_id)

        sections_payload: list[dict[str, Any]] = []
        for section in self.sections.for_variant(inputs.report_variant):
            finding_ids = sorted(finding_ids_by_section.get(section.section_id, []))
            card_ids: list[str] = []
            for finding_id in finding_ids:
                f = next(x for x in findings if x["finding_id"] == finding_id)
                card_id = f"finding:{finding_id}"
                cards.append({
                    "card_id": card_id,
                    "card_type": "FACT_CARD",
                    "section_id": section.section_id,
                    "title": f["label"],
                    "body": f["display_text"],
                    "finding_ids": [finding_id],
                    "status_label": None,
                })
                card_ids.append(card_id)
            if section.section_id == "summary":
                summary_card_id = "summary:primary"
                cards.append({
                    "card_id": summary_card_id,
                    "card_type": "SUMMARY_CARD",
                    "section_id": "summary",
                    "title": inputs.section_titles.get("summary", "Summary"),
                    "body": "\n".join(inputs.summary_items),
                    "finding_ids": [],
                    "status_label": None,
                })
                card_ids.append(summary_card_id)
            title = inputs.section_titles.get(section.section_id)
            if not title:
                raise CanonicalPayloadBuildError(f"missing approved section title: {section.section_id}")
            sections_payload.append({
                "section_id": section.section_id,
                "title": title,
                "order": section.order,
                "card_ids": card_ids,
                "summary": None,
            })

        prop = dict(inputs.property_identity)
        prop["property_id"] = str(inputs.property_id)
        prop.setdefault("community", "San Tan Heights")
        for optional in ("phase", "builder", "floor_plan"):
            prop.setdefault(optional, None)

        payload = {
            "metadata": {
                "report_schema_version": inputs.report_schema_version,
                "content_contract_version": inputs.content_contract_version,
                "variant_policy_version": inputs.variant_policy_version,
                "report_variant": inputs.report_variant,
                "property_id": str(inputs.property_id),
                "snapshot_id": str(inputs.snapshot_id),
                "verified_through": _iso(inputs.verified_through),
                "market_data_through": _iso(inputs.market_data_through),
                "builder_data_through": _iso(inputs.builder_data_through),
            },
            "property_identity": prop,
            "summary": list(inputs.summary_items),
            "sections": sections_payload,
            "findings": sorted(findings, key=lambda x: (x["section_id"], x["finding_type"], x["finding_id"])),
            "cards": cards,
            "media_slots": list(inputs.media_slots),
            "diagram_slots": list(inputs.diagram_slots),
            "glossary": [
                {"term_id": x.term_id, "label": x.label, "definition": x.definition}
                for x in glossary
            ],
            "evidence_disclosures": list(inputs.evidence_disclosures),
            "disclaimers": list(inputs.disclaimers),
            "branding_reference": {
                "brand_profile_id": inputs.brand_profile_id,
                "brand_version": inputs.brand_version,
            },
            "lineage": {
                "snapshot_id": str(inputs.snapshot_id),
                "dependency_manifest_hash": dependency_manifest.manifest_hash,
            },
        }
        self.schema.validate(payload)
        return payload
