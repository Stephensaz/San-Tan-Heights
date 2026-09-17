from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from types import MappingProxyType
from typing import Iterable, Mapping

import yaml

from src.shared.canonical_json import canonical_json

_EXPECTED_ID = "STH-PDF-TEMPLATE-v1.0"
_EXPECTED_VERSION = "1.0.0"
_EXPECTED_STATUS = "LOCKED"
_EXPECTED_PAGE_SIZE = "LETTER"
_EXPECTED_RULES = {
    "preserve_semantic_order": True,
    "allow_content_omission": False,
    "allow_audience_reclassification": False,
    "allow_pdf_specific_fact_changes": False,
    "repeat_header": True,
    "repeat_footer": True,
    "keep_section_heading_with_first_block": True,
    "allow_section_body_split": True,
}


@dataclass(frozen=True)
class PdfPageGeometry:
    size: str
    width_pt: float
    height_pt: float
    margin_top_pt: float
    margin_right_pt: float
    margin_bottom_pt: float
    margin_left_pt: float
    header_height_pt: float
    footer_height_pt: float

    @property
    def body_width_pt(self) -> float:
        return self.width_pt - self.margin_left_pt - self.margin_right_pt

    @property
    def body_height_pt(self) -> float:
        return (
            self.height_pt
            - self.margin_top_pt
            - self.margin_bottom_pt
            - self.header_height_pt
            - self.footer_height_pt
        )


@dataclass(frozen=True)
class PdfTemplateRegistry:
    template_id: str
    version: str
    status: str
    page: PdfPageGeometry
    rules: Mapping[str, bool]
    fingerprint: str

    @classmethod
    def load(cls, path: str | Path) -> "PdfTemplateRegistry":
        raw = yaml.safe_load(Path(path).read_text())
        if not isinstance(raw, dict):
            raise ValueError("PDF template registry must be an object")
        if raw.get("pdf_template_id") != _EXPECTED_ID:
            raise ValueError("unexpected PDF template id")
        if str(raw.get("version")) != _EXPECTED_VERSION:
            raise ValueError("unexpected PDF template version")
        if raw.get("status") != _EXPECTED_STATUS:
            raise ValueError("PDF template registry must be LOCKED")
        if raw.get("rules") != _EXPECTED_RULES:
            raise ValueError("PDF template rules do not match locked contract")

        page_raw = raw.get("page") or {}
        if not isinstance(page_raw, dict) or page_raw.get("size") != _EXPECTED_PAGE_SIZE:
            raise ValueError("PDF template requires locked LETTER page geometry")
        numeric_keys = (
            "width_pt",
            "height_pt",
            "margin_top_pt",
            "margin_right_pt",
            "margin_bottom_pt",
            "margin_left_pt",
            "header_height_pt",
            "footer_height_pt",
        )
        values: dict[str, float] = {}
        for key in numeric_keys:
            value = page_raw.get(key)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
                raise ValueError(f"PDF page geometry {key} must be positive")
            values[key] = float(value)

        page = PdfPageGeometry(size=_EXPECTED_PAGE_SIZE, **values)
        if page.body_width_pt <= 0 or page.body_height_pt <= 0:
            raise ValueError("PDF page geometry leaves no usable body area")

        payload = {
            "pdf_template_id": _EXPECTED_ID,
            "version": _EXPECTED_VERSION,
            "status": _EXPECTED_STATUS,
            "page": {"size": page.size, **values},
            "rules": _EXPECTED_RULES,
        }
        return cls(
            template_id=_EXPECTED_ID,
            version=_EXPECTED_VERSION,
            status=_EXPECTED_STATUS,
            page=page,
            rules=MappingProxyType(dict(_EXPECTED_RULES)),
            fingerprint=sha256(canonical_json(payload).encode("utf-8")).hexdigest(),
        )


@dataclass(frozen=True)
class PdfTemplatePlan:
    template_id: str
    semantic_order: tuple[str, ...]
    page: PdfPageGeometry
    repeat_header: bool
    repeat_footer: bool
    keep_section_heading_with_first_block: bool
    allow_section_body_split: bool

    def canonical_payload(self) -> dict[str, object]:
        return {
            "template_id": self.template_id,
            "semantic_order": list(self.semantic_order),
            "page": self.page.__dict__,
            "repeat_header": self.repeat_header,
            "repeat_footer": self.repeat_footer,
            "keep_section_heading_with_first_block": self.keep_section_heading_with_first_block,
            "allow_section_body_split": self.allow_section_body_split,
        }

    @property
    def fingerprint(self) -> str:
        return sha256(canonical_json(self.canonical_payload()).encode("utf-8")).hexdigest()


class PdfTemplateFoundation:
    def __init__(self, registry: PdfTemplateRegistry) -> None:
        self.registry = registry

    def plan(self, semantic_order: Iterable[str]) -> PdfTemplatePlan:
        order = tuple(str(item) for item in semantic_order)
        if any(not item.strip() for item in order):
            raise ValueError("PDF semantic order identifiers cannot be blank")
        if len(set(order)) != len(order):
            raise ValueError("PDF semantic order identifiers must be unique")
        return PdfTemplatePlan(
            template_id=self.registry.template_id,
            semantic_order=order,
            page=self.registry.page,
            repeat_header=self.registry.rules["repeat_header"],
            repeat_footer=self.registry.rules["repeat_footer"],
            keep_section_heading_with_first_block=self.registry.rules["keep_section_heading_with_first_block"],
            allow_section_body_split=self.registry.rules["allow_section_body_split"],
        )
