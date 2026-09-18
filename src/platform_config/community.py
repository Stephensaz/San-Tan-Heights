from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import yaml


@dataclass(frozen=True)
class CommunityConfig:
    community_id: str
    display_name: str
    state: str
    county: str
    property_id_prefix: str
    listing_service: str
    baseline_id: str
    baseline_version: str
    baseline_manifest_fingerprint: str


def load_community_config(path: str | Path) -> CommunityConfig:
    raw=yaml.safe_load(Path(path).read_text())
    if raw.get("community_config_id")!="STH-COMMUNITY-CONFIG-v1.0" or raw.get("status")!="FROZEN":
        raise ValueError("community configuration must be frozen v1.0")
    c=raw["community"]; s=raw["source_systems"]; b=raw["baseline"]
    if not c["community_id"] or not c["property_id_prefix"]:
        raise ValueError("community identity configuration incomplete")
    if len(b["baseline_manifest_fingerprint"])!=64:
        raise ValueError("baseline fingerprint invalid")
    return CommunityConfig(
        str(c["community_id"]),str(c["display_name"]),str(c["state"]),str(c["county"]),
        str(c["property_id_prefix"]),str(s["listing_service"]),str(b["baseline_id"]),
        str(b["baseline_version"]),str(b["baseline_manifest_fingerprint"])
    )
