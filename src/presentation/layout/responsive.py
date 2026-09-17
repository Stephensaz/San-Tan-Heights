from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from types import MappingProxyType
from typing import Iterable, Mapping

import yaml

from src.presentation.tokens import DesignTokenRegistry
from src.shared.canonical_json import canonical_json

_EXPECTED_ID = "STH-RESPONSIVE-LAYOUT-v1.0"
_EXPECTED_VERSION = "1.0.0"
_EXPECTED_STATUS = "LOCKED"
_EXPECTED_RULES = {
    "preserve_semantic_order": True,
    "allow_content_hiding": False,
    "allow_audience_reclassification": False,
    "allow_semantic_reordering": False,
    "allow_viewport_specific_fact_changes": False,
}


@dataclass(frozen=True)
class ResponsiveMode:
    name: str
    min_width: int
    max_width: int
    card_columns: int
    media_columns: int
    gutter_token: str


@dataclass(frozen=True)
class ResponsiveLayoutRegistry:
    registry_id: str
    version: str
    status: str
    modes: tuple[ResponsiveMode, ...]
    rules: Mapping[str, bool]
    fingerprint: str

    @classmethod
    def load(cls, path: str | Path) -> "ResponsiveLayoutRegistry":
        raw = yaml.safe_load(Path(path).read_text())
        if not isinstance(raw, dict):
            raise ValueError("responsive layout registry must be an object")
        if raw.get("layout_registry_id") != _EXPECTED_ID:
            raise ValueError("unexpected responsive layout registry id")
        if str(raw.get("version")) != _EXPECTED_VERSION:
            raise ValueError("unexpected responsive layout registry version")
        if raw.get("status") != _EXPECTED_STATUS:
            raise ValueError("responsive layout registry must be LOCKED")
        if raw.get("rules") != _EXPECTED_RULES:
            raise ValueError("responsive layout rules do not match locked contract")

        modes_raw = raw.get("modes") or {}
        if not isinstance(modes_raw, dict) or not modes_raw:
            raise ValueError("responsive layout modes cannot be empty")

        modes: list[ResponsiveMode] = []
        for name, spec in modes_raw.items():
            if not isinstance(spec, dict):
                raise ValueError(f"responsive mode {name} must be an object")
            mode = ResponsiveMode(
                name=str(name),
                min_width=int(spec["min_width"]),
                max_width=int(spec["max_width"]),
                card_columns=int(spec["card_columns"]),
                media_columns=int(spec["media_columns"]),
                gutter_token=str(spec["gutter_token"]),
            )
            if mode.min_width <= 0 or mode.max_width < mode.min_width:
                raise ValueError(f"invalid responsive width range: {mode.name}")
            if mode.card_columns <= 0 or mode.media_columns <= 0:
                raise ValueError(f"responsive columns must be positive: {mode.name}")
            modes.append(mode)

        modes.sort(key=lambda item: item.min_width)
        for previous, current in zip(modes, modes[1:]):
            if current.min_width != previous.max_width + 1:
                raise ValueError("responsive layout ranges must be contiguous and non-overlapping")

        payload = {
            "layout_registry_id": _EXPECTED_ID,
            "version": _EXPECTED_VERSION,
            "status": _EXPECTED_STATUS,
            "modes": [mode.__dict__ for mode in modes],
            "rules": _EXPECTED_RULES,
        }
        fingerprint = sha256(canonical_json(payload).encode("utf-8")).hexdigest()
        return cls(
            registry_id=_EXPECTED_ID,
            version=_EXPECTED_VERSION,
            status=_EXPECTED_STATUS,
            modes=tuple(modes),
            rules=MappingProxyType(dict(_EXPECTED_RULES)),
            fingerprint=fingerprint,
        )


@dataclass(frozen=True)
class ResponsiveLayoutPlan:
    mode: str
    viewport_width: int
    card_columns: int
    media_columns: int
    gutter_px: float
    content_max_width_px: float
    semantic_order: tuple[str, ...]

    def canonical_payload(self) -> dict[str, object]:
        return {
            "mode": self.mode,
            "viewport_width": self.viewport_width,
            "card_columns": self.card_columns,
            "media_columns": self.media_columns,
            "gutter_px": self.gutter_px,
            "content_max_width_px": self.content_max_width_px,
            "semantic_order": list(self.semantic_order),
        }

    @property
    def fingerprint(self) -> str:
        return sha256(canonical_json(self.canonical_payload()).encode("utf-8")).hexdigest()


class ResponsiveLayoutRuntime:
    def __init__(self, registry: ResponsiveLayoutRegistry, tokens: DesignTokenRegistry) -> None:
        self.registry = registry
        self.tokens = tokens
        for mode in registry.modes:
            if mode.gutter_token not in tokens.spacing:
                raise ValueError(f"unknown design-token gutter: {mode.gutter_token}")

    def plan(self, *, viewport_width: int, semantic_order: Iterable[str]) -> ResponsiveLayoutPlan:
        if isinstance(viewport_width, bool) or not isinstance(viewport_width, int):
            raise ValueError("viewport_width must be an integer")
        mode = next(
            (item for item in self.registry.modes if item.min_width <= viewport_width <= item.max_width),
            None,
        )
        if mode is None:
            raise ValueError("viewport_width is outside the certified responsive range")

        order = tuple(str(item) for item in semantic_order)
        if any(not item.strip() for item in order):
            raise ValueError("semantic order identifiers cannot be blank")
        if len(set(order)) != len(order):
            raise ValueError("semantic order identifiers must be unique")

        gutter = self.tokens.spacing[mode.gutter_token]
        available = max(float(viewport_width) - 2 * gutter, 1.0)
        content_max = min(self.tokens.layout["content_max_width"], available)
        return ResponsiveLayoutPlan(
            mode=mode.name,
            viewport_width=viewport_width,
            card_columns=mode.card_columns,
            media_columns=mode.media_columns,
            gutter_px=gutter,
            content_max_width_px=content_max,
            semantic_order=order,
        )
