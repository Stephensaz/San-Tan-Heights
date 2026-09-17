from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from types import MappingProxyType
from typing import Mapping

import yaml

from src.presentation.pdf import AgentPdfDocument, PublicPdfDocument, SellerPdfDocument
from src.presentation.pdf.foundation import PdfPageGeometry
from src.shared.canonical_json import canonical_json

_EXPECTED_ID = "STH-PRINT-TEMPLATES-v1.0"
_EXPECTED_VERSION = "1.0.0"
_EXPECTED_STATUS = "LOCKED"
_EXPECTED_AUDIENCES = {
    "AGENT": "agent-print-v1",
    "SELLER": "seller-print-v1",
    "PUBLIC": "public-print-v1",
}
_EXPECTED_PAGE = {"size": "LETTER", "width_pt": 612.0, "height_pt": 792.0}
_EXPECTED_RULES = {
    "preserve_semantic_order": True,
    "allow_content_omission": False,
    "allow_audience_reclassification": False,
    "allow_print_specific_fact_changes": False,
    "repeat_header": True,
    "repeat_footer": True,
    "keep_section_heading_with_first_block": True,
    "avoid_card_split": True,
}


@dataclass(frozen=True)
class PrintTemplateRegistry:
    registry_id: str
    version: str
    status: str
    audiences: Mapping[str, str]
    page_size: str
    page_width_pt: float
    page_height_pt: float
    rules: Mapping[str, bool]
    fingerprint: str

    @classmethod
    def load(cls, path: str | Path) -> "PrintTemplateRegistry":
        raw = yaml.safe_load(Path(path).read_text())
        if not isinstance(raw, dict):
            raise ValueError("print template registry must be an object")
        if raw.get("print_template_id") != _EXPECTED_ID:
            raise ValueError("unexpected print template id")
        if str(raw.get("version")) != _EXPECTED_VERSION:
            raise ValueError("unexpected print template version")
        if raw.get("status") != _EXPECTED_STATUS:
            raise ValueError("print template registry must be LOCKED")
        if raw.get("audiences") != _EXPECTED_AUDIENCES:
            raise ValueError("print template audiences do not match locked contract")
        if raw.get("rules") != _EXPECTED_RULES:
            raise ValueError("print template rules do not match locked contract")

        page = raw.get("page")
        if not isinstance(page, dict):
            raise ValueError("print template page must be an object")
        normalized_page = {
            "size": page.get("size"),
            "width_pt": float(page.get("width_pt", 0)),
            "height_pt": float(page.get("height_pt", 0)),
        }
        if normalized_page != _EXPECTED_PAGE:
            raise ValueError("print template requires locked LETTER page geometry")

        payload = {
            "print_template_id": _EXPECTED_ID,
            "version": _EXPECTED_VERSION,
            "status": _EXPECTED_STATUS,
            "audiences": _EXPECTED_AUDIENCES,
            "page": _EXPECTED_PAGE,
            "rules": _EXPECTED_RULES,
        }
        return cls(
            registry_id=_EXPECTED_ID,
            version=_EXPECTED_VERSION,
            status=_EXPECTED_STATUS,
            audiences=MappingProxyType(dict(_EXPECTED_AUDIENCES)),
            page_size=_EXPECTED_PAGE["size"],
            page_width_pt=_EXPECTED_PAGE["width_pt"],
            page_height_pt=_EXPECTED_PAGE["height_pt"],
            rules=MappingProxyType(dict(_EXPECTED_RULES)),
            fingerprint=sha256(canonical_json(payload).encode("utf-8")).hexdigest(),
        )


@dataclass(frozen=True)
class PrintTemplatePlan:
    audience: str
    template_key: str
    source_document_fingerprint: str
    semantic_order: tuple[str, ...]
    page: PdfPageGeometry
    repeat_header: bool
    repeat_footer: bool
    keep_section_heading_with_first_block: bool
    avoid_card_split: bool

    def canonical_payload(self) -> dict[str, object]:
        return {
            "audience": self.audience,
            "template_key": self.template_key,
            "source_document_fingerprint": self.source_document_fingerprint,
            "semantic_order": list(self.semantic_order),
            "page": self.page.__dict__,
            "repeat_header": self.repeat_header,
            "repeat_footer": self.repeat_footer,
            "keep_section_heading_with_first_block": self.keep_section_heading_with_first_block,
            "avoid_card_split": self.avoid_card_split,
        }

    @property
    def fingerprint(self) -> str:
        return sha256(canonical_json(self.canonical_payload()).encode("utf-8")).hexdigest()


class PrintTemplateRuntime:
    """Bind an already-governed PDF document to its locked audience print template."""

    def __init__(self, registry: PrintTemplateRegistry) -> None:
        self.registry = registry

    def plan(
        self,
        document: AgentPdfDocument | SellerPdfDocument | PublicPdfDocument,
    ) -> PrintTemplatePlan:
        audience = self._audience_for(document)
        self._validate_page(document.template.page)

        section_order = tuple(section.section_id for section in document.sections)
        if section_order != document.template.semantic_order:
            raise ValueError("PDF document section order does not match its certified semantic order")

        return PrintTemplatePlan(
            audience=audience,
            template_key=self.registry.audiences[audience],
            source_document_fingerprint=document.fingerprint,
            semantic_order=document.template.semantic_order,
            page=document.template.page,
            repeat_header=self.registry.rules["repeat_header"],
            repeat_footer=self.registry.rules["repeat_footer"],
            keep_section_heading_with_first_block=self.registry.rules[
                "keep_section_heading_with_first_block"
            ],
            avoid_card_split=self.registry.rules["avoid_card_split"],
        )

    @staticmethod
    def _audience_for(document: object) -> str:
        if isinstance(document, AgentPdfDocument):
            return "AGENT"
        if isinstance(document, SellerPdfDocument):
            return "SELLER"
        if isinstance(document, PublicPdfDocument):
            return "PUBLIC"
        raise ValueError("print template runtime requires a certified Agent, Seller, or Public PDF document")

    def _validate_page(self, page: PdfPageGeometry) -> None:
        if (
            page.size != self.registry.page_size
            or page.width_pt != self.registry.page_width_pt
            or page.height_pt != self.registry.page_height_pt
        ):
            raise ValueError("PDF document page geometry does not match locked print geometry")
