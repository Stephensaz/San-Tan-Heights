from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from types import MappingProxyType
from typing import Mapping
from uuid import UUID

import yaml

from src.presentation.package import PresentationAudience
from src.shared.canonical_json import canonical_json

_EXPECTED_ID = "STH-PROPERTY-ROUTING-v1.0"
_EXPECTED_VERSION = "1.0.0"
_EXPECTED_STATUS = "LOCKED"
_EXPECTED_BASE_PATH = "/properties"
_EXPECTED_SEGMENTS = {"AGENT": "agent", "SELLER": "seller", "PUBLIC": "public"}
_EXPECTED_RULES = {
    "canonical_property_uuid_required": True,
    "route_is_version_independent": True,
    "route_is_identity_only": True,
    "route_does_not_authorize_access": True,
    "allow_address_in_route": False,
    "allow_report_version_in_route": False,
    "allow_presentation_hash_in_route": False,
}


@dataclass(frozen=True)
class PropertyRoutingRegistry:
    registry_id: str
    version: str
    status: str
    base_path: str
    audience_segments: Mapping[str, str]
    rules: Mapping[str, bool]
    fingerprint: str

    @classmethod
    def load(cls, path: str | Path) -> "PropertyRoutingRegistry":
        raw = yaml.safe_load(Path(path).read_text())
        if not isinstance(raw, dict):
            raise ValueError("property routing registry must be an object")
        if raw.get("property_routing_id") != _EXPECTED_ID:
            raise ValueError("unexpected property routing id")
        if str(raw.get("version")) != _EXPECTED_VERSION:
            raise ValueError("unexpected property routing version")
        if raw.get("status") != _EXPECTED_STATUS:
            raise ValueError("property routing registry must be LOCKED")
        if raw.get("base_path") != _EXPECTED_BASE_PATH:
            raise ValueError("property routing base path does not match locked contract")
        if raw.get("audience_segments") != _EXPECTED_SEGMENTS:
            raise ValueError("property routing audience segments do not match locked contract")
        if raw.get("rules") != _EXPECTED_RULES:
            raise ValueError("property routing rules do not match locked contract")
        payload = {
            "property_routing_id": _EXPECTED_ID,
            "version": _EXPECTED_VERSION,
            "status": _EXPECTED_STATUS,
            "base_path": _EXPECTED_BASE_PATH,
            "audience_segments": _EXPECTED_SEGMENTS,
            "rules": _EXPECTED_RULES,
        }
        return cls(
            registry_id=_EXPECTED_ID,
            version=_EXPECTED_VERSION,
            status=_EXPECTED_STATUS,
            base_path=_EXPECTED_BASE_PATH,
            audience_segments=MappingProxyType(dict(_EXPECTED_SEGMENTS)),
            rules=MappingProxyType(dict(_EXPECTED_RULES)),
            fingerprint=sha256(canonical_json(payload).encode("utf-8")).hexdigest(),
        )


@dataclass(frozen=True)
class StablePropertyRoute:
    property_id: str
    audience: PresentationAudience
    path: str
    registry_fingerprint: str

    def canonical_payload(self) -> dict[str, str]:
        return {
            "property_id": self.property_id,
            "audience": self.audience.value,
            "path": self.path,
            "registry_fingerprint": self.registry_fingerprint,
        }

    @property
    def fingerprint(self) -> str:
        return sha256(canonical_json(self.canonical_payload()).encode("utf-8")).hexdigest()


class StablePropertyRouter:
    """Deterministic, version-independent routing over canonical property identity.

    A route identifies a property and intended presentation audience only. It is not
    an authorization decision and never embeds report versions, addresses, findings,
    or presentation hashes.
    """

    def __init__(self, registry: PropertyRoutingRegistry) -> None:
        self.registry = registry
        self._audience_by_segment = {
            segment: PresentationAudience[name]
            for name, segment in self.registry.audience_segments.items()
        }

    def build(self, property_id: str, audience: PresentationAudience) -> StablePropertyRoute:
        canonical_id = self._canonical_property_id(property_id)
        if not isinstance(audience, PresentationAudience):
            raise ValueError("audience must be a PresentationAudience")
        segment = self.registry.audience_segments[audience.value]
        path = f"{self.registry.base_path}/{canonical_id}/{segment}"
        return StablePropertyRoute(
            property_id=canonical_id,
            audience=audience,
            path=path,
            registry_fingerprint=self.registry.fingerprint,
        )

    def resolve(self, path: str) -> StablePropertyRoute:
        if not isinstance(path, str) or not path.startswith(self.registry.base_path + "/"):
            raise ValueError("path does not match stable property routing contract")
        if "?" in path or "#" in path:
            raise ValueError("stable property route must not contain query or fragment data")
        remainder = path[len(self.registry.base_path) + 1 :]
        parts = remainder.split("/")
        if len(parts) != 2 or not all(parts):
            raise ValueError("path does not match stable property routing contract")
        property_id, segment = parts
        try:
            audience = self._audience_by_segment[segment]
        except KeyError as exc:
            raise ValueError("unknown presentation audience route segment") from exc
        route = self.build(property_id, audience)
        if route.path != path:
            raise ValueError("property route is not canonical")
        return route

    @staticmethod
    def _canonical_property_id(value: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("property_id is required")
        try:
            parsed = UUID(value)
        except (ValueError, AttributeError) as exc:
            raise ValueError("property_id must be a canonical UUID") from exc
        canonical = str(parsed)
        if value != canonical:
            raise ValueError("property_id must use canonical lowercase UUID form")
        return canonical
