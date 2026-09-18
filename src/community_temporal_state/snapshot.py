from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from datetime import datetime
import hashlib
import json
import re
from pathlib import Path
from typing import Iterable, Mapping, Sequence

import yaml

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def _canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _hash(value: object) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _parse_ts(value: str, label: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{label} must be ISO-8601") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{label} must be timezone-aware")
    return parsed


def _validate_fp(value: str, label: str) -> None:
    if not isinstance(value, str) or not _SHA256_RE.fullmatch(value):
        raise ValueError(f"{label} must be a lowercase SHA-256 fingerprint")


def load_snapshot_registry(path: str | Path) -> dict:
    data = yaml.safe_load(Path(path).read_text())
    if data["status"] != "FROZEN" or data["ticket"] != "M13-001":
        raise ValueError("M13-001 snapshot registry must be FROZEN")
    return data


@dataclass(frozen=True)
class TemporalManifestEntry:
    entry_type: str
    entry_id: str
    effective_at: str
    known_at: str
    fingerprint: str

    @property
    def sort_key(self) -> tuple[str, str, str, str, str]:
        return (self.entry_type, self.entry_id, self.effective_at, self.known_at, self.fingerprint)


@dataclass(frozen=True)
class PropertyStateProjection:
    property_id: str
    identity_fingerprint: str
    phase_fingerprint: str
    spatial_fingerprint: str
    intelligence_fingerprint: str
    freshness_state: str
    exclusion_codes: tuple[str, ...]
    conflict_codes: tuple[str, ...]
    projection_fingerprint: str


@dataclass(frozen=True)
class CommunityStateSnapshot:
    snapshot_id: str
    community_id: str
    observation_time: str
    knowledge_cutoff: str
    materialized_at: str
    baseline_snapshot_id: str | None
    m12_release_certification_root: str
    source_manifest: tuple[TemporalManifestEntry, ...]
    policy_manifest: tuple[TemporalManifestEntry, ...]
    runtime_manifest: tuple[TemporalManifestEntry, ...]
    corpus_property_ids: tuple[str, ...]
    property_states: tuple[PropertyStateProjection, ...]
    exclusions: tuple[str, ...]
    conflicts: tuple[str, ...]
    freshness_state: str
    certification_state: str
    reproducible: bool
    blocking_conditions: tuple[str, ...]
    comparison_eligible: bool
    semantic_hash: str
    record_hash: str


def make_manifest_entry(
    *,
    entry_type: str,
    entry_id: str,
    effective_at: str,
    known_at: str,
    fingerprint: str,
) -> TemporalManifestEntry:
    if not entry_type.strip() or not entry_id.strip():
        raise ValueError("manifest entry_type and entry_id required")
    _parse_ts(effective_at, "manifest effective_at")
    _parse_ts(known_at, "manifest known_at")
    _validate_fp(fingerprint, "manifest fingerprint")
    return TemporalManifestEntry(
        entry_type=entry_type.strip(),
        entry_id=entry_id.strip(),
        effective_at=effective_at,
        known_at=known_at,
        fingerprint=fingerprint,
    )


def make_property_projection(
    *,
    property_id: str,
    identity_fingerprint: str,
    phase_fingerprint: str,
    spatial_fingerprint: str,
    intelligence_fingerprint: str,
    freshness_state: str,
    exclusion_codes: Sequence[str] = (),
    conflict_codes: Sequence[str] = (),
    registry: Mapping[str, object],
) -> PropertyStateProjection:
    if not property_id.strip():
        raise ValueError("property_id required")
    for label, value in (
        ("identity fingerprint", identity_fingerprint),
        ("phase fingerprint", phase_fingerprint),
        ("spatial fingerprint", spatial_fingerprint),
        ("intelligence fingerprint", intelligence_fingerprint),
    ):
        _validate_fp(value, label)
    allowed = set(registry["policy"]["allowed_freshness_states"])
    if freshness_state not in allowed:
        raise ValueError("unsupported freshness state")
    exclusions = tuple(sorted(set(str(x) for x in exclusion_codes if str(x).strip())))
    conflicts = tuple(sorted(set(str(x) for x in conflict_codes if str(x).strip())))
    payload = {
        "property_id": property_id.strip(),
        "identity_fingerprint": identity_fingerprint,
        "phase_fingerprint": phase_fingerprint,
        "spatial_fingerprint": spatial_fingerprint,
        "intelligence_fingerprint": intelligence_fingerprint,
        "freshness_state": freshness_state,
        "exclusion_codes": exclusions,
        "conflict_codes": conflicts,
    }
    return PropertyStateProjection(
        **payload,
        projection_fingerprint=_hash(payload),
    )


def _manifest_payload(entries: Iterable[TemporalManifestEntry]) -> tuple[dict, ...]:
    return tuple(asdict(x) for x in sorted(entries, key=lambda x: x.sort_key))


def _property_payload(entries: Iterable[PropertyStateProjection]) -> tuple[dict, ...]:
    return tuple(asdict(x) for x in sorted(entries, key=lambda x: x.property_id))


def _semantic_payload(snapshot: CommunityStateSnapshot) -> dict:
    return {
        "community_id": snapshot.community_id,
        "observation_time": snapshot.observation_time,
        "knowledge_cutoff": snapshot.knowledge_cutoff,
        "baseline_snapshot_id": snapshot.baseline_snapshot_id,
        "m12_release_certification_root": snapshot.m12_release_certification_root,
        "source_manifest": _manifest_payload(snapshot.source_manifest),
        "policy_manifest": _manifest_payload(snapshot.policy_manifest),
        "runtime_manifest": _manifest_payload(snapshot.runtime_manifest),
        "corpus_property_ids": tuple(sorted(snapshot.corpus_property_ids)),
        "property_states": _property_payload(snapshot.property_states),
        "exclusions": tuple(sorted(snapshot.exclusions)),
        "conflicts": tuple(sorted(snapshot.conflicts)),
        "freshness_state": snapshot.freshness_state,
    }


def _validate_manifest_temporality(
    *,
    entries: Iterable[TemporalManifestEntry],
    observation_time: datetime,
    knowledge_cutoff: datetime,
) -> None:
    for entry in entries:
        effective = _parse_ts(entry.effective_at, "manifest effective_at")
        known = _parse_ts(entry.known_at, "manifest known_at")
        if effective > observation_time:
            raise ValueError("future-effective source cannot enter snapshot")
        if known > knowledge_cutoff:
            raise ValueError("knowledge cutoff violation")


def _compute_blocking_conditions(
    *,
    source_drift: bool,
    policy_drift: bool,
    runtime_drift: bool,
    conflicts: Sequence[str],
    reproducible: bool,
) -> tuple[str, ...]:
    blocking: set[str] = set()
    if source_drift:
        blocking.add("SOURCE_DRIFT")
    if policy_drift:
        blocking.add("POLICY_DRIFT")
    if runtime_drift:
        blocking.add("RUNTIME_DRIFT")
    if conflicts:
        blocking.add("UNRESOLVED_CONFLICT")
    if not reproducible:
        blocking.add("NONREPRODUCIBLE")
    return tuple(sorted(blocking))


def build_community_state_snapshot(
    *,
    snapshot_id: str,
    community_id: str,
    observation_time: str,
    knowledge_cutoff: str,
    materialized_at: str,
    baseline_snapshot_id: str | None,
    m12_release_certified: bool,
    m12_release_certification_root: str,
    source_manifest: Sequence[TemporalManifestEntry],
    policy_manifest: Sequence[TemporalManifestEntry],
    runtime_manifest: Sequence[TemporalManifestEntry],
    property_states: Sequence[PropertyStateProjection],
    exclusions: Sequence[str] = (),
    conflicts: Sequence[str] = (),
    freshness_state: str = "CURRENT",
    source_drift: bool = False,
    policy_drift: bool = False,
    runtime_drift: bool = False,
    registry: Mapping[str, object],
) -> CommunityStateSnapshot:
    if not snapshot_id.strip() or not community_id.strip():
        raise ValueError("snapshot_id and community_id required")
    if m12_release_certified is not True:
        raise ValueError("released certified M12 baseline required")
    expected_root = str(registry["released_m12"]["certification_root"])
    if m12_release_certification_root != expected_root:
        raise ValueError("M12 release certification root mismatch")
    _validate_fp(m12_release_certification_root, "M12 release certification root")

    observation = _parse_ts(observation_time, "observation_time")
    cutoff = _parse_ts(knowledge_cutoff, "knowledge_cutoff")
    materialized = _parse_ts(materialized_at, "materialized_at")
    if cutoff > observation:
        raise ValueError("knowledge_cutoff cannot be after observation_time")
    if materialized < cutoff:
        raise ValueError("materialized_at cannot precede knowledge_cutoff")

    allowed_freshness = set(registry["policy"]["allowed_freshness_states"])
    if freshness_state not in allowed_freshness:
        raise ValueError("unsupported snapshot freshness state")

    all_manifest = tuple(source_manifest) + tuple(policy_manifest) + tuple(runtime_manifest)
    _validate_manifest_temporality(
        entries=all_manifest,
        observation_time=observation,
        knowledge_cutoff=cutoff,
    )

    if len({(x.entry_type, x.entry_id) for x in all_manifest}) != len(all_manifest):
        raise ValueError("manifest entry identity must be unique across snapshot")

    props = tuple(sorted(property_states, key=lambda x: x.property_id))
    property_ids = tuple(x.property_id for x in props)
    if len(set(property_ids)) != len(property_ids):
        raise ValueError("property projection must resolve exactly once per property")

    exclusions_tuple = tuple(sorted(set(str(x) for x in exclusions if str(x).strip())))
    conflicts_tuple = tuple(sorted(set(str(x) for x in conflicts if str(x).strip())))
    reproducible = not (source_drift or policy_drift or runtime_drift)
    blocking = _compute_blocking_conditions(
        source_drift=source_drift,
        policy_drift=policy_drift,
        runtime_drift=runtime_drift,
        conflicts=conflicts_tuple,
        reproducible=reproducible,
    )

    draft = CommunityStateSnapshot(
        snapshot_id=snapshot_id.strip(),
        community_id=community_id.strip(),
        observation_time=observation_time,
        knowledge_cutoff=knowledge_cutoff,
        materialized_at=materialized_at,
        baseline_snapshot_id=baseline_snapshot_id,
        m12_release_certification_root=m12_release_certification_root,
        source_manifest=tuple(sorted(source_manifest, key=lambda x: x.sort_key)),
        policy_manifest=tuple(sorted(policy_manifest, key=lambda x: x.sort_key)),
        runtime_manifest=tuple(sorted(runtime_manifest, key=lambda x: x.sort_key)),
        corpus_property_ids=property_ids,
        property_states=props,
        exclusions=exclusions_tuple,
        conflicts=conflicts_tuple,
        freshness_state=freshness_state,
        certification_state="DRAFT",
        reproducible=reproducible,
        blocking_conditions=blocking,
        comparison_eligible=False,
        semantic_hash="",
        record_hash="",
    )
    semantic_hash = _hash(_semantic_payload(draft))
    record_payload = {
        **_semantic_payload(draft),
        "snapshot_id": draft.snapshot_id,
        "materialized_at": draft.materialized_at,
        "certification_state": draft.certification_state,
        "reproducible": draft.reproducible,
        "blocking_conditions": draft.blocking_conditions,
        "comparison_eligible": draft.comparison_eligible,
        "semantic_hash": semantic_hash,
    }
    return replace(
        draft,
        semantic_hash=semantic_hash,
        record_hash=_hash(record_payload),
    )


def validate_snapshot_replay(snapshot: CommunityStateSnapshot) -> bool:
    return _hash(_semantic_payload(snapshot)) == snapshot.semantic_hash


def certify_snapshot(
    snapshot: CommunityStateSnapshot,
    *,
    registry: Mapping[str, object],
) -> CommunityStateSnapshot:
    if snapshot.certification_state not in {"DRAFT", "VALIDATED"}:
        raise ValueError("only DRAFT or VALIDATED snapshot may be certified")
    if not validate_snapshot_replay(snapshot):
        raise ValueError("snapshot is nonreproducible")
    if snapshot.blocking_conditions:
        raise ValueError("snapshot has blocking conditions")
    eligible_freshness = set(registry["policy"]["comparison_eligible_freshness"])
    comparison_eligible = snapshot.freshness_state in eligible_freshness
    certified = replace(
        snapshot,
        certification_state="CERTIFIED",
        comparison_eligible=comparison_eligible,
    )
    record_payload = {
        **_semantic_payload(certified),
        "snapshot_id": certified.snapshot_id,
        "materialized_at": certified.materialized_at,
        "certification_state": certified.certification_state,
        "reproducible": certified.reproducible,
        "blocking_conditions": certified.blocking_conditions,
        "comparison_eligible": certified.comparison_eligible,
        "semantic_hash": certified.semantic_hash,
    }
    return replace(certified, record_hash=_hash(record_payload))


def validate_comparison_eligibility(
    snapshot: CommunityStateSnapshot,
    *,
    registry: Mapping[str, object],
) -> None:
    expected_state = registry["policy"]["comparison_eligible_certification_state"]
    if snapshot.certification_state != expected_state:
        raise ValueError("comparison requires CERTIFIED snapshot")
    if not snapshot.comparison_eligible:
        raise ValueError("snapshot is not comparison eligible")
    if snapshot.blocking_conditions:
        raise ValueError("blocked snapshot cannot be compared")
    if not validate_snapshot_replay(snapshot):
        raise ValueError("nonreproducible snapshot cannot be compared")
