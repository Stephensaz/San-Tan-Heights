from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
import re
from typing import Iterable, Mapping
import yaml

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_COMMUNITY_ID = re.compile(r"^[A-Z][A-Z0-9_]*$")
_STATE = re.compile(r"^[A-Z]{2}$")


def _hash(payload: object) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return sha256(raw).hexdigest()


@dataclass(frozen=True)
class CommunityOnboardingInput:
    onboarding_id: str
    community_id: str
    display_name: str
    state: str
    county: str
    property_id_prefix: str
    listing_service: str
    parcel_authority: str
    recorder_authority: str
    parent_platform_version: str
    parent_platform_fingerprint: str
    community_specific: tuple[str, ...]
    source_specific: tuple[str, ...]


@dataclass(frozen=True)
class BootstrapArtifacts:
    community_config: Mapping[str, object]
    onboarding_manifest: Mapping[str, object]
    community_config_fingerprint: str
    onboarding_manifest_fingerprint: str
    bootstrap_fingerprint: str


def load_onboarding_contract(path: str | Path) -> dict:
    raw = yaml.safe_load(Path(path).read_text())
    if raw.get("contract_id") != "STH-COMMUNITY-ONBOARDING":
        raise ValueError("unexpected onboarding contract id")
    if str(raw.get("version")) != "1.0.0" or raw.get("status") != "LOCKED":
        raise ValueError("community onboarding contract must be locked v1.0")
    if raw.get("ticket") != "M10-003":
        raise ValueError("community onboarding contract ticket mismatch")
    return raw


def _clean_values(values: Iterable[str], field: str) -> tuple[str, ...]:
    cleaned = tuple(sorted(set(str(x).strip() for x in values if str(x).strip())))
    if not cleaned:
        raise ValueError(f"{field} assumptions must be explicit and nonempty")
    return cleaned


def validate_onboarding_input(data: CommunityOnboardingInput, contract: Mapping[str, object]) -> CommunityOnboardingInput:
    if not data.onboarding_id.strip():
        raise ValueError("onboarding_id required")
    if not _COMMUNITY_ID.fullmatch(data.community_id):
        raise ValueError("community_id must be upper snake case")
    protected = str(contract["validation"]["reject_protected_community_id"])
    if data.community_id == protected:
        raise ValueError("protected community may not be onboarded as a new community")
    if not data.display_name.strip():
        raise ValueError("display_name required")
    if not _STATE.fullmatch(data.state):
        raise ValueError("state must be a two-letter uppercase code")
    for name, value in (
        ("county", data.county),
        ("property_id_prefix", data.property_id_prefix),
        ("listing_service", data.listing_service),
        ("parcel_authority", data.parcel_authority),
        ("recorder_authority", data.recorder_authority),
        ("parent_platform_version", data.parent_platform_version),
    ):
        if not str(value).strip():
            raise ValueError(f"{name} required")
    if not _SHA256.fullmatch(data.parent_platform_fingerprint):
        raise ValueError("parent platform fingerprint must be sha256")

    community_specific = _clean_values(data.community_specific, "community_specific")
    source_specific = _clean_values(data.source_specific, "source_specific")
    return CommunityOnboardingInput(
        onboarding_id=data.onboarding_id.strip(),
        community_id=data.community_id,
        display_name=data.display_name.strip(),
        state=data.state,
        county=data.county.strip(),
        property_id_prefix=data.property_id_prefix.strip(),
        listing_service=data.listing_service.strip(),
        parcel_authority=data.parcel_authority.strip(),
        recorder_authority=data.recorder_authority.strip(),
        parent_platform_version=data.parent_platform_version.strip(),
        parent_platform_fingerprint=data.parent_platform_fingerprint,
        community_specific=community_specific,
        source_specific=source_specific,
    )


def generate_bootstrap(*, data: CommunityOnboardingInput, contract: Mapping[str, object]) -> BootstrapArtifacts:
    data = validate_onboarding_input(data, contract)

    community_config = {
        "community_config_id": f"{data.community_id}-COMMUNITY-CONFIG-v1.0",
        "version": "1.0.0",
        "status": "BOOTSTRAP",
        "community": {
            "community_id": data.community_id,
            "display_name": data.display_name,
            "state": data.state,
            "county": data.county,
            "property_id_prefix": data.property_id_prefix,
        },
        "source_systems": {
            "listing_service": data.listing_service,
            "parcel_authority": data.parcel_authority,
            "recorder_authority": data.recorder_authority,
        },
        "lineage": {
            "parent_platform_version": data.parent_platform_version,
            "parent_platform_fingerprint": data.parent_platform_fingerprint,
        },
        "assumptions": {
            "community_specific": list(data.community_specific),
            "source_specific": list(data.source_specific),
        },
    }
    config_fp = _hash(community_config)

    onboarding_manifest = {
        "onboarding_manifest_id": f"{data.community_id}-ONBOARDING-MANIFEST-v1.0",
        "onboarding_id": data.onboarding_id,
        "community_id": data.community_id,
        "contract_id": str(contract["contract_id"]),
        "contract_version": str(contract["version"]),
        "parent_platform_version": data.parent_platform_version,
        "parent_platform_fingerprint": data.parent_platform_fingerprint,
        "community_config_fingerprint": config_fp,
        "generated_artifacts": ["community_config", "onboarding_manifest"],
        "deterministic": True,
    }
    manifest_fp = _hash(onboarding_manifest)
    bootstrap_fp = _hash({
        "community_config_fingerprint": config_fp,
        "onboarding_manifest_fingerprint": manifest_fp,
    })
    return BootstrapArtifacts(
        community_config=community_config,
        onboarding_manifest=onboarding_manifest,
        community_config_fingerprint=config_fp,
        onboarding_manifest_fingerprint=manifest_fp,
        bootstrap_fingerprint=bootstrap_fp,
    )


def assert_no_protected_defaults(artifacts: BootstrapArtifacts, protected_tokens: Iterable[str]) -> None:
    raw = json.dumps(
        {
            "community_config": artifacts.community_config,
            "onboarding_manifest": artifacts.onboarding_manifest,
        },
        sort_keys=True,
    )
    leaked = tuple(sorted(token for token in protected_tokens if token and token in raw))
    if leaked:
        raise ValueError(f"protected community default leakage detected: {leaked}")
