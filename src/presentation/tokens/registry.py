from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from types import MappingProxyType
from typing import Mapping

import yaml

from src.shared.canonical_json import canonical_json

_EXPECTED_ID = "STH-DESIGN-TOKENS-v1.0"
_EXPECTED_VERSION = "1.0.0"
_EXPECTED_STATUS = "LOCKED"
_REQUIRED_GROUPS = ("colors", "spacing", "radius", "typography", "layout")


@dataclass(frozen=True)
class DesignTokenRegistry:
    registry_id: str
    version: str
    status: str
    colors: Mapping[str, str]
    spacing: Mapping[str, float]
    radius: Mapping[str, float]
    typography: Mapping[str, float]
    layout: Mapping[str, float]
    fingerprint: str

    @classmethod
    def load(cls, path: str | Path) -> "DesignTokenRegistry":
        payload = yaml.safe_load(Path(path).read_text())
        if not isinstance(payload, dict):
            raise ValueError("design token registry must be an object")
        if payload.get("token_registry_id") != _EXPECTED_ID:
            raise ValueError("unexpected design token registry id")
        if payload.get("version") != _EXPECTED_VERSION:
            raise ValueError("unexpected design token registry version")
        if payload.get("status") != _EXPECTED_STATUS:
            raise ValueError("design token registry must be LOCKED")
        for group in _REQUIRED_GROUPS:
            if not isinstance(payload.get(group), dict) or not payload[group]:
                raise ValueError(f"design token group {group} is required")

        colors = dict(payload["colors"])
        for key, value in colors.items():
            if not isinstance(value, str) or len(value) != 7 or not value.startswith("#"):
                raise ValueError(f"invalid color token: {key}")
            try:
                int(value[1:], 16)
            except ValueError as exc:
                raise ValueError(f"invalid color token: {key}") from exc
            if value != value.upper():
                raise ValueError(f"color token must use uppercase hex: {key}")

        numeric_groups: dict[str, dict[str, float]] = {}
        for group in ("spacing", "radius", "typography", "layout"):
            normalized: dict[str, float] = {}
            for key, value in payload[group].items():
                if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
                    raise ValueError(f"{group}.{key} must be positive")
                normalized[str(key)] = float(value)
            numeric_groups[group] = normalized

        fingerprint_payload = {
            "token_registry_id": payload["token_registry_id"],
            "version": payload["version"],
            "status": payload["status"],
            "colors": colors,
            **numeric_groups,
        }
        fingerprint = sha256(canonical_json(fingerprint_payload).encode("utf-8")).hexdigest()
        return cls(
            registry_id=_EXPECTED_ID,
            version=_EXPECTED_VERSION,
            status=_EXPECTED_STATUS,
            colors=MappingProxyType(colors),
            spacing=MappingProxyType(numeric_groups["spacing"]),
            radius=MappingProxyType(numeric_groups["radius"]),
            typography=MappingProxyType(numeric_groups["typography"]),
            layout=MappingProxyType(numeric_groups["layout"]),
            fingerprint=fingerprint,
        )
