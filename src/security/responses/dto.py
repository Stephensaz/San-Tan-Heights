from __future__ import annotations
from dataclasses import asdict, dataclass
from typing import Any

@dataclass(frozen=True)
class PublicReportResponse:
    property_id: str
    report_variant: str
    verified_through: str
    property_identity: dict[str, Any]
    summary: tuple[str, ...]
    sections: tuple[dict[str, Any], ...]
    cards: tuple[dict[str, Any], ...]
    findings: tuple[dict[str, Any], ...]
    media_slots: tuple[dict[str, Any], ...]
    diagram_slots: tuple[dict[str, Any], ...]
    glossary: tuple[dict[str, Any], ...]
    disclaimers: tuple[str, ...]
    branding_reference: dict[str, Any]
    def to_dict(self) -> dict[str, Any]: return asdict(self)

@dataclass(frozen=True)
class SellerReportResponse:
    property_id: str
    report_variant: str
    verified_through: str
    market_data_through: str | None
    builder_data_through: str | None
    property_identity: dict[str, Any]
    summary: tuple[str, ...]
    sections: tuple[dict[str, Any], ...]
    cards: tuple[dict[str, Any], ...]
    findings: tuple[dict[str, Any], ...]
    media_slots: tuple[dict[str, Any], ...]
    diagram_slots: tuple[dict[str, Any], ...]
    glossary: tuple[dict[str, Any], ...]
    evidence_disclosures: tuple[dict[str, Any], ...]
    disclaimers: tuple[str, ...]
    branding_reference: dict[str, Any]
    def to_dict(self) -> dict[str, Any]: return asdict(self)

@dataclass(frozen=True)
class AgentReportResponse:
    property_id: str
    report_variant: str
    report_schema_version: str
    content_contract_version: str
    variant_policy_version: str
    snapshot_id: str
    verified_through: str
    market_data_through: str | None
    builder_data_through: str | None
    property_identity: dict[str, Any]
    summary: tuple[str, ...]
    sections: tuple[dict[str, Any], ...]
    cards: tuple[dict[str, Any], ...]
    findings: tuple[dict[str, Any], ...]
    media_slots: tuple[dict[str, Any], ...]
    diagram_slots: tuple[dict[str, Any], ...]
    glossary: tuple[dict[str, Any], ...]
    evidence_disclosures: tuple[dict[str, Any], ...]
    disclaimers: tuple[str, ...]
    branding_reference: dict[str, Any]
    lineage: dict[str, Any]
    def to_dict(self) -> dict[str, Any]: return asdict(self)
