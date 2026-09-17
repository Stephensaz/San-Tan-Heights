from __future__ import annotations

from dataclasses import dataclass, replace
from hashlib import sha256
from pathlib import Path
from types import MappingProxyType
from typing import Iterable, Mapping

import yaml

from src.presentation.layout import ResponsiveLayoutPlan
from src.shared.canonical_json import canonical_json

_EXPECTED_ID = "STH-MOBILE-NAVIGATION-v1.0"
_EXPECTED_VERSION = "1.0.0"
_EXPECTED_STATUS = "LOCKED"
_EXPECTED_RULES = {
    "compact_mode_only": True,
    "preserve_semantic_order": True,
    "require_all_sections_reachable": True,
    "allow_initial_collapse": True,
    "allow_content_omission": False,
    "allow_semantic_reordering": False,
    "allow_audience_reclassification": False,
    "allow_collapsed_state_to_change_meaning": False,
}


@dataclass(frozen=True)
class MobileNavigationRegistry:
    registry_id: str
    version: str
    status: str
    rules: Mapping[str, bool]
    fingerprint: str

    @classmethod
    def load(cls, path: str | Path) -> "MobileNavigationRegistry":
        raw = yaml.safe_load(Path(path).read_text())
        if not isinstance(raw, dict):
            raise ValueError("mobile navigation registry must be an object")
        if raw.get("mobile_navigation_id") != _EXPECTED_ID:
            raise ValueError("unexpected mobile navigation registry id")
        if str(raw.get("version")) != _EXPECTED_VERSION:
            raise ValueError("unexpected mobile navigation registry version")
        if raw.get("status") != _EXPECTED_STATUS:
            raise ValueError("mobile navigation registry must be LOCKED")
        if raw.get("rules") != _EXPECTED_RULES:
            raise ValueError("mobile navigation rules do not match locked contract")
        payload = {
            "mobile_navigation_id": _EXPECTED_ID,
            "version": _EXPECTED_VERSION,
            "status": _EXPECTED_STATUS,
            "rules": _EXPECTED_RULES,
        }
        return cls(
            registry_id=_EXPECTED_ID,
            version=_EXPECTED_VERSION,
            status=_EXPECTED_STATUS,
            rules=MappingProxyType(dict(_EXPECTED_RULES)),
            fingerprint=sha256(canonical_json(payload).encode("utf-8")).hexdigest(),
        )


@dataclass(frozen=True)
class MobileSectionState:
    section_id: str
    position: int
    expanded: bool
    reachable: bool = True


@dataclass(frozen=True)
class MobileNavigationState:
    sections: tuple[MobileSectionState, ...]
    active_section_id: str | None

    def __post_init__(self) -> None:
        ids = tuple(section.section_id for section in self.sections)
        if any(not value.strip() for value in ids):
            raise ValueError("mobile section identifiers cannot be blank")
        if len(set(ids)) != len(ids):
            raise ValueError("mobile section identifiers must be unique")
        if tuple(section.position for section in self.sections) != tuple(range(len(self.sections))):
            raise ValueError("mobile section positions must preserve canonical order")
        if not all(section.reachable for section in self.sections):
            raise ValueError("all mobile sections must remain reachable")
        if self.active_section_id is not None and self.active_section_id not in ids:
            raise ValueError("active mobile section must be present in navigation")

    def canonical_payload(self) -> dict[str, object]:
        return {
            "sections": [section.__dict__ for section in self.sections],
            "active_section_id": self.active_section_id,
        }

    @property
    def fingerprint(self) -> str:
        return sha256(canonical_json(self.canonical_payload()).encode("utf-8")).hexdigest()


class MobileNavigationRuntime:
    def __init__(self, registry: MobileNavigationRegistry) -> None:
        self.registry = registry

    def build(
        self,
        layout: ResponsiveLayoutPlan,
        *,
        expanded_ids: Iterable[str] = (),
        active_section_id: str | None = None,
    ) -> MobileNavigationState:
        if self.registry.rules["compact_mode_only"] and layout.mode != "COMPACT":
            raise ValueError("mobile navigation requires a COMPACT responsive layout")

        order = tuple(layout.semantic_order)
        expanded = {str(value) for value in expanded_ids}
        unknown = expanded.difference(order)
        if unknown:
            raise ValueError(f"expanded mobile section is not in semantic order: {sorted(unknown)}")
        if active_section_id is not None and active_section_id not in order:
            raise ValueError("active mobile section is not in semantic order")

        sections = tuple(
            MobileSectionState(
                section_id=section_id,
                position=index,
                expanded=section_id in expanded,
                reachable=True,
            )
            for index, section_id in enumerate(order)
        )
        return MobileNavigationState(sections=sections, active_section_id=active_section_id)

    def toggle(self, state: MobileNavigationState, section_id: str) -> MobileNavigationState:
        if section_id not in {section.section_id for section in state.sections}:
            raise ValueError("cannot toggle unknown mobile section")
        sections = tuple(
            replace(section, expanded=not section.expanded) if section.section_id == section_id else section
            for section in state.sections
        )
        return MobileNavigationState(sections=sections, active_section_id=state.active_section_id)

    def activate(self, state: MobileNavigationState, section_id: str) -> MobileNavigationState:
        if section_id not in {section.section_id for section in state.sections}:
            raise ValueError("cannot activate unknown mobile section")
        return MobileNavigationState(sections=state.sections, active_section_id=section_id)
