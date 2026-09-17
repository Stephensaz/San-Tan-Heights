from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import re
from types import MappingProxyType
from typing import Iterable, Mapping

import yaml

from src.shared.canonical_json import canonical_json

_SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_EXPECTED_POLICY_ID = "STH-PRESENTATION-MEDIA-POLICY-v1.0"
_EXPECTED_VERSION = "1.0.0"
_EXPECTED_STATUS = "LOCKED"


@dataclass(frozen=True)
class MediaPolicyRegistry:
    policy_id: str
    version: str
    status: str
    asset_kinds: frozenset[str]
    allowed_content_types: Mapping[str, frozenset[str]]
    allowed_audiences: frozenset[str]
    allowed_channels: frozenset[str]
    rules: Mapping[str, bool]
    fingerprint: str

    @classmethod
    def load(cls, path: str | Path) -> "MediaPolicyRegistry":
        raw = yaml.safe_load(Path(path).read_text())
        if not isinstance(raw, dict):
            raise ValueError("media policy must be an object")
        if raw.get("policy_id") != _EXPECTED_POLICY_ID:
            raise ValueError("unexpected media policy id")
        if str(raw.get("version")) != _EXPECTED_VERSION:
            raise ValueError("unexpected media policy version")
        if raw.get("status") != _EXPECTED_STATUS:
            raise ValueError("media policy must be LOCKED")

        kinds = frozenset(str(v) for v in (raw.get("asset_kinds") or []))
        audiences = frozenset(str(v) for v in (raw.get("allowed_audiences") or []))
        channels = frozenset(str(v) for v in (raw.get("allowed_channels") or []))
        content_types_raw = raw.get("allowed_content_types") or {}
        rules = raw.get("rules") or {}
        if not kinds or not audiences or not channels:
            raise ValueError("media policy enums cannot be empty")
        if set(content_types_raw) != set(kinds):
            raise ValueError("media content type registry must cover every asset kind exactly")

        expected_rules = {
            "require_content_sha256": True,
            "require_source_reference": True,
            "require_accessibility_text": True,
            "allow_remote_fetch": False,
            "allow_content_mutation": False,
            "allow_scope_broadening": False,
            "allow_semantic_inference": False,
        }
        if rules != expected_rules:
            raise ValueError("media policy rules do not match locked contract")

        content_types = {
            str(kind): frozenset(str(v) for v in values)
            for kind, values in content_types_raw.items()
        }
        payload = {
            "policy_id": _EXPECTED_POLICY_ID,
            "version": _EXPECTED_VERSION,
            "status": _EXPECTED_STATUS,
            "asset_kinds": sorted(kinds),
            "allowed_content_types": {k: sorted(content_types[k]) for k in sorted(content_types)},
            "allowed_audiences": sorted(audiences),
            "allowed_channels": sorted(channels),
            "rules": expected_rules,
        }
        fingerprint = sha256(canonical_json(payload).encode("utf-8")).hexdigest()
        return cls(
            policy_id=_EXPECTED_POLICY_ID,
            version=_EXPECTED_VERSION,
            status=_EXPECTED_STATUS,
            asset_kinds=kinds,
            allowed_content_types=MappingProxyType(content_types),
            allowed_audiences=audiences,
            allowed_channels=channels,
            rules=MappingProxyType(dict(expected_rules)),
            fingerprint=fingerprint,
        )


@dataclass(frozen=True)
class MediaAssetDescriptor:
    asset_id: str
    asset_kind: str
    content_type: str
    content_sha256: str
    source_reference: str
    accessibility_text: str
    audiences: frozenset[str]
    channels: frozenset[str]
    caption: str | None = None

    def __post_init__(self) -> None:
        if not _SLUG.fullmatch(self.asset_id):
            raise ValueError("media asset_id must be a lowercase slug")
        if not _SHA256.fullmatch(self.content_sha256):
            raise ValueError("media content_sha256 must be lowercase sha256")
        if not self.source_reference.strip():
            raise ValueError("media source_reference is required")
        if not self.accessibility_text.strip():
            raise ValueError("media accessibility_text is required")
        if not self.audiences or not self.channels:
            raise ValueError("media audiences and channels cannot be empty")
        if self.caption is not None and not self.caption.strip():
            raise ValueError("media caption cannot be blank")

    def canonical_payload(self) -> dict[str, object]:
        return {
            "asset_id": self.asset_id,
            "asset_kind": self.asset_kind,
            "content_type": self.content_type,
            "content_sha256": self.content_sha256,
            "source_reference": self.source_reference,
            "accessibility_text": self.accessibility_text,
            "audiences": sorted(self.audiences),
            "channels": sorted(self.channels),
            "caption": self.caption,
        }


@dataclass(frozen=True)
class MediaManifest:
    policy_fingerprint: str
    assets: tuple[MediaAssetDescriptor, ...]

    def canonical_payload(self) -> dict[str, object]:
        return {
            "policy_fingerprint": self.policy_fingerprint,
            "assets": [asset.canonical_payload() for asset in self.assets],
        }

    @property
    def fingerprint(self) -> str:
        return sha256(canonical_json(self.canonical_payload()).encode("utf-8")).hexdigest()


class MediaPipeline:
    """Immutable manifest pipeline for presentation media.

    This layer validates descriptors and scopes. It does not fetch, transform,
    host, score, classify, or infer meaning from media content.
    """

    def __init__(self, policy: MediaPolicyRegistry) -> None:
        self.policy = policy

    def build_manifest(self, assets: Iterable[MediaAssetDescriptor]) -> MediaManifest:
        items = tuple(assets)
        seen_ids: set[str] = set()
        seen_hashes: dict[str, str] = {}
        for asset in items:
            self._validate_asset(asset)
            if asset.asset_id in seen_ids:
                raise ValueError(f"duplicate media asset_id: {asset.asset_id}")
            seen_ids.add(asset.asset_id)
            prior = seen_hashes.get(asset.content_sha256)
            if prior is not None and prior != asset.asset_id:
                raise ValueError("same media content hash cannot be registered under multiple asset IDs")
            seen_hashes[asset.content_sha256] = asset.asset_id

        ordered = tuple(sorted(items, key=lambda item: item.asset_id))
        return MediaManifest(policy_fingerprint=self.policy.fingerprint, assets=ordered)

    def eligible(self, manifest: MediaManifest, *, audience: str, channel: str) -> MediaManifest:
        if manifest.policy_fingerprint != self.policy.fingerprint:
            raise ValueError("media manifest policy fingerprint mismatch")
        if audience not in self.policy.allowed_audiences:
            raise ValueError(f"unsupported media audience: {audience}")
        if channel not in self.policy.allowed_channels:
            raise ValueError(f"unsupported media channel: {channel}")
        selected = tuple(
            asset for asset in manifest.assets
            if audience in asset.audiences and channel in asset.channels
        )
        return MediaManifest(policy_fingerprint=manifest.policy_fingerprint, assets=selected)

    def _validate_asset(self, asset: MediaAssetDescriptor) -> None:
        if asset.asset_kind not in self.policy.asset_kinds:
            raise ValueError(f"unsupported media asset kind: {asset.asset_kind}")
        if asset.content_type not in self.policy.allowed_content_types[asset.asset_kind]:
            raise ValueError(
                f"content type {asset.content_type} is not allowed for media kind {asset.asset_kind}"
            )
        if not asset.audiences.issubset(self.policy.allowed_audiences):
            raise ValueError("media asset contains unsupported audience scope")
        if not asset.channels.issubset(self.policy.allowed_channels):
            raise ValueError("media asset contains unsupported channel scope")
