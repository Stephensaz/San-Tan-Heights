from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
from typing import Mapping
import yaml


def _hash(payload: object) -> str:
    raw=json.dumps(payload,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode("utf-8")
    return sha256(raw).hexdigest()


@dataclass(frozen=True)
class GovernedProfile:
    profile_id: str
    profile_type: str
    community_id: str
    retained_component_class: str
    payload: Mapping[str, object]
    fingerprint: str


def load_hardening_registry(path: str|Path) -> dict:
    raw=yaml.safe_load(Path(path).read_text())
    if raw.get("hardening_registry_id")!="STH-M10-006-PORTABILITY-HARDENING-v1.0":
        raise ValueError("unexpected M10-006 hardening registry id")
    if str(raw.get("version"))!="1.0.0" or raw.get("status")!="FROZEN":
        raise ValueError("M10-006 hardening registry must be frozen v1.0")
    if raw.get("ticket")!="M10-006":
        raise ValueError("M10-006 hardening registry ticket mismatch")
    return raw


def load_governed_profile(path: str|Path, *, registry: Mapping[str,object]) -> GovernedProfile:
    raw=yaml.safe_load(Path(path).read_text())
    profile_type=str(raw.get("profile_type") or "")
    spec=(registry.get("profile_types") or {}).get(profile_type)
    if not isinstance(spec,dict):
        raise ValueError(f"unregistered portability profile type: {profile_type}")
    for key in spec.get("required_keys") or ():
        if key not in raw or raw[key] in (None,"",[],{}):
            raise ValueError(f"missing required profile key: {key}")
    if raw.get("status")!="HARDENED":
        raise ValueError("portability profile must be HARDENED")
    if str(raw.get("version"))!="1.0.0":
        raise ValueError("portability profile must be version 1.0.0")

    retained=str(spec["retained_component_class"])
    declared=str(raw.get("component_class") or "")
    if declared!=retained:
        raise ValueError("hardening profile changed component classification")

    if profile_type=="LISTING_SOURCE_COMPATIBILITY":
        policy=raw.get("access_policy") or {}
        if policy.get("proprietary_records_used") is not False:
            raise ValueError("listing-source profile may not imply proprietary record access")
        if policy.get("credentials_available") is not False:
            raise ValueError("listing-source profile may not imply credentials")

    payload=dict(raw)
    return GovernedProfile(
        profile_id=str(raw["profile_id"]),
        profile_type=profile_type,
        community_id=str(raw["community_id"]),
        retained_component_class=retained,
        payload=payload,
        fingerprint=_hash(payload),
    )


def validate_disposition_artifacts(
    *,
    repository_root: str|Path,
    registry: Mapping[str,object],
) -> dict[str,GovernedProfile]:
    root=Path(repository_root)
    profiles={}
    seen=set()
    for row in registry.get("dispositions") or ():
        item_id=str(row.get("work_item_id") or "")
        if not item_id or item_id in seen:
            raise ValueError("hardening disposition work item ids must be unique and nonblank")
        seen.add(item_id)
        if row.get("disposition")!="GOVERNED_PROFILE_INPUT" or row.get("post_action")!="CONFIGURE":
            raise ValueError(f"unsupported hardening disposition: {item_id}")
        artifact=str(row.get("hardened_artifact") or "")
        if not artifact or not (root/artifact).is_file():
            raise ValueError(f"missing hardened profile artifact: {artifact or item_id}")
        p=load_governed_profile(root/artifact,registry=registry)
        if p.profile_type!=row.get("profile_type"):
            raise ValueError(f"profile type mismatch: {item_id}")
        if p.retained_component_class!=row.get("prior_class"):
            raise ValueError(f"classification drift during hardening: {item_id}")
        profiles[item_id]=p
    return profiles
