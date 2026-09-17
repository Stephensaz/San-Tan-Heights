from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from types import MappingProxyType
from typing import Mapping

import yaml

from src.presentation.package import PresentationAudience, PresentationChannel
from src.shared.canonical_json import canonical_json

_EXPECTED_BRANDING_ID = "STH-BRANDING-v1.0"
_EXPECTED_VERSION = "1.0.0"
_EXPECTED_STATUS = "LOCKED"
_EXPECTED_BRAND = {
    "brand_id": "SAN_TAN_HEIGHTS",
    "display_name": "San Tan Heights",
    "descriptor": "Property Intelligence",
}
_EXPECTED_TOKEN_REF = {"registry_id": "STH-DESIGN-TOKENS-v1.0", "version": "1.0.0"}
_EXPECTED_RULES = {
    "use_locked_design_tokens_only": True,
    "branding_does_not_change_property_facts": True,
    "branding_does_not_change_audience_eligibility": True,
    "branding_does_not_hide_required_disclosures": True,
    "allow_runtime_color_override": False,
    "allow_runtime_typography_override": False,
}


@dataclass(frozen=True)
class BrandingRegistry:
    registry_id: str
    version: str
    status: str
    brand_id: str
    display_name: str
    descriptor: str
    design_token_registry_id: str
    design_token_version: str
    rules: Mapping[str, bool]
    fingerprint: str

    @classmethod
    def load(cls, path: str | Path) -> "BrandingRegistry":
        raw = yaml.safe_load(Path(path).read_text())
        if not isinstance(raw, dict):
            raise ValueError("branding registry must be an object")
        if raw.get("branding_runtime_id") != _EXPECTED_BRANDING_ID:
            raise ValueError("unexpected branding runtime id")
        if str(raw.get("version")) != _EXPECTED_VERSION:
            raise ValueError("unexpected branding runtime version")
        if raw.get("status") != _EXPECTED_STATUS:
            raise ValueError("branding registry must be LOCKED")
        if raw.get("brand") != _EXPECTED_BRAND:
            raise ValueError("brand identity does not match locked contract")
        if raw.get("design_tokens") != _EXPECTED_TOKEN_REF:
            raise ValueError("design token reference does not match locked contract")
        if raw.get("rules") != _EXPECTED_RULES:
            raise ValueError("branding rules do not match locked contract")
        payload = {
            "branding_runtime_id": _EXPECTED_BRANDING_ID,
            "version": _EXPECTED_VERSION,
            "status": _EXPECTED_STATUS,
            "brand": _EXPECTED_BRAND,
            "design_tokens": _EXPECTED_TOKEN_REF,
            "rules": _EXPECTED_RULES,
        }
        return cls(
            registry_id=_EXPECTED_BRANDING_ID,
            version=_EXPECTED_VERSION,
            status=_EXPECTED_STATUS,
            brand_id=_EXPECTED_BRAND["brand_id"],
            display_name=_EXPECTED_BRAND["display_name"],
            descriptor=_EXPECTED_BRAND["descriptor"],
            design_token_registry_id=_EXPECTED_TOKEN_REF["registry_id"],
            design_token_version=_EXPECTED_TOKEN_REF["version"],
            rules=MappingProxyType(dict(_EXPECTED_RULES)),
            fingerprint=sha256(canonical_json(payload).encode("utf-8")).hexdigest(),
        )


@dataclass(frozen=True)
class DesignTokenSet:
    registry_id: str
    version: str
    status: str
    colors: Mapping[str, str]
    spacing: Mapping[str, int]
    radius: Mapping[str, int]
    typography: Mapping[str, int]
    layout: Mapping[str, int]
    fingerprint: str

    @classmethod
    def load(cls, path: str | Path) -> "DesignTokenSet":
        raw = yaml.safe_load(Path(path).read_text())
        if not isinstance(raw, dict):
            raise ValueError("design token registry must be an object")
        if raw.get("token_registry_id") != "STH-DESIGN-TOKENS-v1.0":
            raise ValueError("unexpected design token registry id")
        if str(raw.get("version")) != "1.0.0":
            raise ValueError("unexpected design token version")
        if raw.get("status") != "LOCKED":
            raise ValueError("design token registry must be LOCKED")
        required = ("colors", "spacing", "radius", "typography", "layout")
        if any(not isinstance(raw.get(name), dict) or not raw[name] for name in required):
            raise ValueError("design token registry is incomplete")
        payload = {name: raw[name] for name in ("token_registry_id", "version", "status", *required)}
        return cls(
            registry_id=raw["token_registry_id"],
            version=str(raw["version"]),
            status=raw["status"],
            colors=MappingProxyType(dict(raw["colors"])),
            spacing=MappingProxyType(dict(raw["spacing"])),
            radius=MappingProxyType(dict(raw["radius"])),
            typography=MappingProxyType(dict(raw["typography"])),
            layout=MappingProxyType(dict(raw["layout"])),
            fingerprint=sha256(canonical_json(payload).encode("utf-8")).hexdigest(),
        )


@dataclass(frozen=True)
class BrandingPlan:
    brand_id: str
    display_name: str
    descriptor: str
    audience: PresentationAudience
    channel: PresentationChannel
    branding_registry_fingerprint: str
    design_token_fingerprint: str
    colors: Mapping[str, str]
    spacing: Mapping[str, int]
    radius: Mapping[str, int]
    typography: Mapping[str, int]
    layout: Mapping[str, int]

    def canonical_payload(self) -> dict[str, object]:
        return {
            "brand_id": self.brand_id,
            "display_name": self.display_name,
            "descriptor": self.descriptor,
            "audience": self.audience.value,
            "channel": self.channel.value,
            "branding_registry_fingerprint": self.branding_registry_fingerprint,
            "design_token_fingerprint": self.design_token_fingerprint,
            "colors": dict(self.colors),
            "spacing": dict(self.spacing),
            "radius": dict(self.radius),
            "typography": dict(self.typography),
            "layout": dict(self.layout),
        }

    @property
    def fingerprint(self) -> str:
        return sha256(canonical_json(self.canonical_payload()).encode("utf-8")).hexdigest()


class BrandingRuntime:
    """Apply only the locked brand identity and locked design tokens."""

    def __init__(self, registry: BrandingRegistry, tokens: DesignTokenSet) -> None:
        if tokens.registry_id != registry.design_token_registry_id or tokens.version != registry.design_token_version:
            raise ValueError("branding registry and design token registry are incompatible")
        self.registry = registry
        self.tokens = tokens

    def plan(self, audience: PresentationAudience, channel: PresentationChannel) -> BrandingPlan:
        if not isinstance(audience, PresentationAudience):
            raise ValueError("audience must be a PresentationAudience")
        if not isinstance(channel, PresentationChannel):
            raise ValueError("channel must be a PresentationChannel")
        return BrandingPlan(
            brand_id=self.registry.brand_id,
            display_name=self.registry.display_name,
            descriptor=self.registry.descriptor,
            audience=audience,
            channel=channel,
            branding_registry_fingerprint=self.registry.fingerprint,
            design_token_fingerprint=self.tokens.fingerprint,
            colors=self.tokens.colors,
            spacing=self.tokens.spacing,
            radius=self.tokens.radius,
            typography=self.tokens.typography,
            layout=self.tokens.layout,
        )
