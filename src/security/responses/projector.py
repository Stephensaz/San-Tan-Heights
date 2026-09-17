from __future__ import annotations
from copy import deepcopy
from typing import Any
from .dto import AgentReportResponse, SellerReportResponse, PublicReportResponse
from .negative_fields import NegativeFieldProtector

class ResponseProjectionError(ValueError):
    pass

def _require_payload_variant(payload: dict[str, Any], expected: str) -> dict[str, Any]:
    metadata = payload.get("metadata") or {}
    actual = metadata.get("report_variant")
    if actual != expected:
        raise ResponseProjectionError(f"REPORT_VARIANT_MISMATCH:{actual}:{expected}")
    return metadata

def _base_finding_public(f: dict[str, Any]) -> dict[str, Any]:
    return {k: deepcopy(f.get(k)) for k in ("finding_id","finding_type","label","display_text","section_id","status_label","limitation")}

def _base_finding_seller(f: dict[str, Any]) -> dict[str, Any]:
    out = _base_finding_public(f)
    out["confidence_label"] = deepcopy(f.get("confidence_label"))
    return out

def _sanitize_evidence_seller(e: dict[str, Any]) -> dict[str, Any]:
    return {k: deepcopy(e.get(k)) for k in ("disclosure_id","finding_id","source_category","verified_at","limitation")}

class AudienceResponseProjector:
    """Whitelist-only projection from canonical report payloads into explicit audience DTOs."""
    def __init__(self, protector: NegativeFieldProtector | None = None):
        self.protector = protector or NegativeFieldProtector()

    def public(self, payload: dict[str, Any]) -> PublicReportResponse:
        m = _require_payload_variant(payload, "PUBLIC")
        dto = PublicReportResponse(
            property_id=str(m["property_id"]), report_variant="PUBLIC", verified_through=str(m["verified_through"]),
            property_identity=deepcopy(payload["property_identity"]), summary=tuple(payload["summary"]),
            sections=tuple(deepcopy(payload["sections"])), cards=tuple(deepcopy(payload["cards"])),
            findings=tuple(_base_finding_public(f) for f in payload["findings"]),
            media_slots=tuple(deepcopy(payload["media_slots"])), diagram_slots=tuple(deepcopy(payload["diagram_slots"])),
            glossary=tuple(deepcopy(payload["glossary"])), disclaimers=tuple(payload["disclaimers"]),
            branding_reference=deepcopy(payload["branding_reference"]),
        )
        self.protector.require_clean("PUBLIC", dto.to_dict())
        return dto

    def seller(self, payload: dict[str, Any]) -> SellerReportResponse:
        m = _require_payload_variant(payload, "SELLER")
        dto = SellerReportResponse(
            property_id=str(m["property_id"]), report_variant="SELLER", verified_through=str(m["verified_through"]),
            market_data_through=m.get("market_data_through"), builder_data_through=m.get("builder_data_through"),
            property_identity=deepcopy(payload["property_identity"]), summary=tuple(payload["summary"]),
            sections=tuple(deepcopy(payload["sections"])), cards=tuple(deepcopy(payload["cards"])),
            findings=tuple(_base_finding_seller(f) for f in payload["findings"]),
            media_slots=tuple(deepcopy(payload["media_slots"])), diagram_slots=tuple(deepcopy(payload["diagram_slots"])),
            glossary=tuple(deepcopy(payload["glossary"])),
            evidence_disclosures=tuple(_sanitize_evidence_seller(e) for e in payload["evidence_disclosures"]),
            disclaimers=tuple(payload["disclaimers"]), branding_reference=deepcopy(payload["branding_reference"]),
        )
        self.protector.require_clean("SELLER", dto.to_dict())
        return dto

    def agent(self, payload: dict[str, Any]) -> AgentReportResponse:
        m = _require_payload_variant(payload, "AGENT")
        dto = AgentReportResponse(
            property_id=str(m["property_id"]), report_variant="AGENT",
            report_schema_version=str(m["report_schema_version"]), content_contract_version=str(m["content_contract_version"]),
            variant_policy_version=str(m["variant_policy_version"]), snapshot_id=str(m["snapshot_id"]),
            verified_through=str(m["verified_through"]), market_data_through=m.get("market_data_through"),
            builder_data_through=m.get("builder_data_through"), property_identity=deepcopy(payload["property_identity"]),
            summary=tuple(payload["summary"]), sections=tuple(deepcopy(payload["sections"])), cards=tuple(deepcopy(payload["cards"])),
            findings=tuple(deepcopy(payload["findings"])), media_slots=tuple(deepcopy(payload["media_slots"])),
            diagram_slots=tuple(deepcopy(payload["diagram_slots"])), glossary=tuple(deepcopy(payload["glossary"])),
            evidence_disclosures=tuple(deepcopy(payload["evidence_disclosures"])), disclaimers=tuple(payload["disclaimers"]),
            branding_reference=deepcopy(payload["branding_reference"]), lineage=deepcopy(payload["lineage"]),
        )
        self.protector.require_clean("AGENT", dto.to_dict())
        return dto

    def project(self, audience_role: str, payload: dict[str, Any]):
        if audience_role == "PUBLIC": return self.public(payload)
        if audience_role == "SELLER": return self.seller(payload)
        if audience_role in {"AGENT","OPERATIONS","ADMIN"}: return self.agent(payload)
        raise ResponseProjectionError("UNKNOWN_RESPONSE_AUDIENCE")
