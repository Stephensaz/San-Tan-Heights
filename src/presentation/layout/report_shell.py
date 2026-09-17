from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from typing import Iterable

from src.presentation.components import ComponentPrimitive
from src.shared.canonical_json import canonical_json

SECTION_ORDER = (
    "property_header",
    "summary",
    "property_dna",
    "lot_location",
    "home_characteristics",
    "market_buyer_context",
    "evidence",
    "changes",
    "freshness",
    "glossary_disclosures",
)
_ORDER_INDEX = {name: index for index, name in enumerate(SECTION_ORDER)}


@dataclass(frozen=True)
class ReportSectionSlot:
    section_key: str
    component: ComponentPrimitive

    def __post_init__(self) -> None:
        if self.section_key not in _ORDER_INDEX:
            raise ValueError(f"unsupported report section: {self.section_key}")


@dataclass(frozen=True)
class ReportLayoutShell:
    property_id: str
    report_id: str
    sections: tuple[ReportSectionSlot, ...]

    def __post_init__(self) -> None:
        if not self.property_id.strip() or not self.report_id.strip():
            raise ValueError("property_id and report_id are required")
        sections = tuple(self.sections)
        keys = [item.section_key for item in sections]
        if len(keys) != len(set(keys)):
            raise ValueError("report section keys must be unique")
        if keys != sorted(keys, key=_ORDER_INDEX.__getitem__):
            raise ValueError("report sections must preserve canonical order")
        object.__setattr__(self, "sections", sections)

    @classmethod
    def compose(cls, *, property_id: str, report_id: str, sections: Iterable[ReportSectionSlot]) -> "ReportLayoutShell":
        ordered = tuple(sorted(tuple(sections), key=lambda item: _ORDER_INDEX[item.section_key]))
        return cls(property_id=property_id, report_id=report_id, sections=ordered)

    def canonical_payload(self) -> dict[str, object]:
        return {
            "property_id": self.property_id,
            "report_id": self.report_id,
            "sections": [
                {"section_key": slot.section_key, "component": slot.component.canonical_payload()}
                for slot in self.sections
            ],
        }

    @property
    def fingerprint(self) -> str:
        return sha256(canonical_json(self.canonical_payload()).encode("utf-8")).hexdigest()
