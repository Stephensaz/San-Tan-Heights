from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from datetime import datetime
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

import yaml

from src.community_temporal_state.snapshot import (
    CommunityStateSnapshot,
    PropertyStateProjection,
    TemporalManifestEntry,
    validate_comparison_eligibility,
    validate_snapshot_replay,
)


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


def load_delta_registry(path: str | Path) -> dict:
    data = yaml.safe_load(Path(path).read_text())
    if data.get("status") != "FROZEN" or data.get("ticket") != "M13-002":
        raise ValueError("M13-002 delta registry must be FROZEN")
    if data.get("delta_registry_id") != "STH-M13-002-COMMUNITY-DELTA-v1.0":
        raise ValueError("unexpected M13-002 delta registry id")
    return data


@dataclass(frozen=True)
class ChangeCause:
    cause: str
    basis: str


@dataclass(frozen=True)
class FieldChange:
    change_id: str
    scope: str
    object_type: str
    object_id: str
    domain: str
    field_path: str
    before_value: Any
    after_value: Any
    classification: str
    change_cause: str
    causation_basis: str
    first_observed_at: str
    effective_at: str
    recorded_at: str
    detected_at: str
    materiality: str
    source_snapshot_ids: tuple[str, str]
    source_semantic_hashes: tuple[str, str]
    evidence_fingerprints: tuple[str, ...]
    potentially_stale: bool
    explanation: str
    change_fingerprint: str


@dataclass(frozen=True)
class ImpactEdge:
    source_change_fingerprint: str
    affected_object_type: str
    affected_object_id: str
    reason_code: str
    potentially_stale: bool
    edge_fingerprint: str


@dataclass(frozen=True)
class CommunityDelta:
    delta_id: str
    community_id: str
    before_snapshot_id: str
    after_snapshot_id: str
    before_snapshot_semantic_hash: str
    after_snapshot_semantic_hash: str
    before_observation_time: str
    after_observation_time: str
    detected_at: str
    materiality_rules_version: str
    changes: tuple[FieldChange, ...]
    impact_edges: tuple[ImpactEdge, ...]
    highest_materiality: str
    lineage_fingerprints: tuple[str, ...]
    certification_state: str
    reproducible: bool
    delta_fingerprint: str


_PROPERTY_FIELDS = (
    ("identity_fingerprint", "IDENTITY"),
    ("phase_fingerprint", "PHASE"),
    ("spatial_fingerprint", "LOCATION_DNA"),
    ("intelligence_fingerprint", "INTELLIGENCE"),
    ("freshness_state", "INTELLIGENCE"),
    ("exclusion_codes", "GOVERNANCE"),
    ("conflict_codes", "GOVERNANCE"),
)

_MATERIALITY_ORDER = {
    "INFORMATIONAL": 0,
    "LOW": 1,
    "MODERATE": 2,
    "HIGH": 3,
    "CRITICAL": 4,
}


def _cause_for(
    key: str,
    *,
    registry: Mapping[str, object],
    cause_overrides: Mapping[str, ChangeCause] | None,
    inferred: ChangeCause | None = None,
) -> ChangeCause:
    if cause_overrides and key in cause_overrides:
        value = cause_overrides[key]
        if value.cause not in set(registry["policy"]["change_causes"]):
            raise ValueError("unsupported change cause")
        if value.basis not in set(registry["policy"]["causation_basis"]):
            raise ValueError("unsupported causation basis")
        return value
    if inferred is not None:
        return inferred
    return ChangeCause("UNKNOWN", "UNKNOWN_CAUSE")


def _effective_at(
    key: str,
    *,
    effective_at_overrides: Mapping[str, str] | None,
    exact_effective_at: str | None = None,
) -> str:
    if exact_effective_at is not None:
        _parse_ts(exact_effective_at, "effective_at")
        return exact_effective_at
    if effective_at_overrides and key in effective_at_overrides:
        value = effective_at_overrides[key]
        if value == "UNKNOWN":
            return value
        _parse_ts(value, "effective_at")
        return value
    return "UNKNOWN"


def _materiality(domain: str, classification: str, registry: Mapping[str, object]) -> str:
    overrides = registry["materiality"]["classification_overrides"]
    if classification in overrides:
        result = str(overrides[classification])
    else:
        result = str(registry["materiality"]["domain_defaults"][domain])
    if result not in set(registry["policy"]["materiality_levels"]):
        raise ValueError("materiality rule produced unsupported value")
    return result


def _classify_value(field_path: str, before: Any, after: Any) -> str:
    if before == after:
        return "UNCHANGED"
    if field_path == "freshness_state":
        if before == "UNKNOWN" and after != "UNKNOWN":
            return "BECAME_KNOWN"
        if before != "UNKNOWN" and after == "UNKNOWN":
            return "BECAME_UNKNOWN"
    if field_path == "conflict_codes":
        b, a = set(before or ()), set(after or ())
        if not b and a:
            return "CONFLICT_INTRODUCED"
        if b and not a:
            return "CONFLICT_RESOLVED"
    if field_path == "exclusion_codes":
        b, a = set(before or ()), set(after or ())
        if a - b and not (b - a):
            return "SUPPRESSED"
        if b - a and not (a - b):
            return "REACTIVATED"
    return "MODIFIED"


def _explanation(
    *,
    object_type: str,
    object_id: str,
    field_path: str,
    classification: str,
) -> str:
    return f"{object_type} {object_id} field {field_path} classified as {classification}."


def _make_change(
    *,
    delta_id: str,
    ordinal: int,
    scope: str,
    object_type: str,
    object_id: str,
    domain: str,
    field_path: str,
    before_value: Any,
    after_value: Any,
    classification: str,
    cause: ChangeCause,
    before: CommunityStateSnapshot,
    after: CommunityStateSnapshot,
    detected_at: str,
    registry: Mapping[str, object],
    effective_at_overrides: Mapping[str, str] | None,
    cause_key: str,
    evidence_fingerprints: Sequence[str],
    exact_effective_at: str | None = None,
) -> FieldChange:
    if classification not in set(registry["policy"]["change_classifications"]):
        raise ValueError("unsupported change classification")
    materiality = _materiality(domain, classification, registry)
    potentially_stale = (
        classification != "UNCHANGED"
        and domain in set(registry["potential_staleness"]["domains"])
    )
    payload = {
        "change_id": f"{delta_id}:C{ordinal:06d}",
        "scope": scope,
        "object_type": object_type,
        "object_id": object_id,
        "domain": domain,
        "field_path": field_path,
        "before_value": before_value,
        "after_value": after_value,
        "classification": classification,
        "change_cause": cause.cause,
        "causation_basis": cause.basis,
        "first_observed_at": after.observation_time,
        "effective_at": _effective_at(
            cause_key,
            effective_at_overrides=effective_at_overrides,
            exact_effective_at=exact_effective_at,
        ),
        "recorded_at": after.materialized_at,
        "detected_at": detected_at,
        "materiality": materiality,
        "source_snapshot_ids": (before.snapshot_id, after.snapshot_id),
        "source_semantic_hashes": (before.semantic_hash, after.semantic_hash),
        "evidence_fingerprints": tuple(sorted(set(evidence_fingerprints))),
        "potentially_stale": potentially_stale,
        "explanation": _explanation(
            object_type=object_type,
            object_id=object_id,
            field_path=field_path,
            classification=classification,
        ),
    }
    return FieldChange(**payload, change_fingerprint=_hash(payload))


def _manifest_map(snapshot: CommunityStateSnapshot, kind: str) -> dict[tuple[str, str], TemporalManifestEntry]:
    rows = getattr(snapshot, f"{kind}_manifest")
    return {(x.entry_type, x.entry_id): x for x in rows}


def _manifest_domain(kind: str) -> str:
    return {"source": "SOURCE", "policy": "POLICY", "runtime": "RUNTIME"}[kind]


def _manifest_inferred_cause(
    *,
    kind: str,
    before_entry: TemporalManifestEntry | None,
    after_entry: TemporalManifestEntry | None,
    before: CommunityStateSnapshot,
) -> ChangeCause | None:
    if kind == "policy":
        return ChangeCause("CLASSIFICATION_CHANGE", "RULE_DRIVEN")
    if kind == "runtime":
        return ChangeCause("ENGINE_CHANGE", "ENGINE_DRIVEN")
    if kind == "source" and before_entry is None and after_entry is not None:
        known = _parse_ts(after_entry.known_at, "manifest known_at")
        effective = _parse_ts(after_entry.effective_at, "manifest effective_at")
        old_cutoff = _parse_ts(before.knowledge_cutoff, "knowledge_cutoff")
        old_observation = _parse_ts(before.observation_time, "observation_time")
        if known > old_cutoff and effective <= old_observation:
            return ChangeCause("NEWLY_OBSERVED_FACT", "DATA_DRIVEN")
    return None


def _impact_edge(change: FieldChange, *, registry: Mapping[str, object]) -> ImpactEdge | None:
    if not change.potentially_stale:
        return None
    if change.scope == "PROPERTY":
        affected_id = change.object_id
    else:
        affected_id = "COMMUNITY"
    payload = {
        "source_change_fingerprint": change.change_fingerprint,
        "affected_object_type": registry["potential_staleness"]["affected_object_type"],
        "affected_object_id": affected_id,
        "reason_code": f"{change.domain}_CHANGE_MAY_STALE_DERIVED_STATE",
        "potentially_stale": True,
    }
    return ImpactEdge(**payload, edge_fingerprint=_hash(payload))


def build_community_delta(
    *,
    delta_id: str,
    before: CommunityStateSnapshot,
    after: CommunityStateSnapshot,
    detected_at: str,
    snapshot_registry: Mapping[str, object],
    delta_registry: Mapping[str, object],
    cause_overrides: Mapping[str, ChangeCause] | None = None,
    effective_at_overrides: Mapping[str, str] | None = None,
) -> CommunityDelta:
    if not delta_id.strip():
        raise ValueError("delta_id required")
    validate_comparison_eligibility(before, registry=snapshot_registry)
    validate_comparison_eligibility(after, registry=snapshot_registry)
    if not validate_snapshot_replay(before) or not validate_snapshot_replay(after):
        raise ValueError("snapshot replay validation failed")
    if before.community_id != after.community_id:
        raise ValueError("snapshot community mismatch")
    if before.m12_release_certification_root != after.m12_release_certification_root:
        raise ValueError("snapshot M12 lineage mismatch")
    before_obs = _parse_ts(before.observation_time, "before observation_time")
    after_obs = _parse_ts(after.observation_time, "after observation_time")
    detected = _parse_ts(detected_at, "detected_at")
    if after_obs <= before_obs:
        raise ValueError("after snapshot must be chronologically later")
    if detected < after_obs:
        raise ValueError("detected_at cannot precede after observation_time")

    changes: list[FieldChange] = []
    ordinal = 0

    def add_change(**kwargs):
        nonlocal ordinal
        ordinal += 1
        changes.append(_make_change(delta_id=delta_id, ordinal=ordinal, before=before, after=after,
                                    detected_at=detected_at, registry=delta_registry,
                                    effective_at_overrides=effective_at_overrides, **kwargs))

    community_fields = (
        ("freshness_state", "COMMUNITY"),
        ("exclusions", "GOVERNANCE"),
        ("conflicts", "GOVERNANCE"),
    )
    for field_path, domain in community_fields:
        b = getattr(before, field_path)
        a = getattr(after, field_path)
        classification = _classify_value(
            "conflict_codes" if field_path == "conflicts"
            else "exclusion_codes" if field_path == "exclusions"
            else field_path,
            b, a,
        )
        key = f"COMMUNITY:{before.community_id}:{field_path}"
        cause = _cause_for(key, registry=delta_registry, cause_overrides=cause_overrides)
        add_change(
            scope="COMMUNITY", object_type="COMMUNITY", object_id=before.community_id,
            domain=domain, field_path=field_path, before_value=b, after_value=a,
            classification=classification, cause=cause, cause_key=key,
            evidence_fingerprints=(before.semantic_hash, after.semantic_hash),
        )

    b_props = {x.property_id: x for x in before.property_states}
    a_props = {x.property_id: x for x in after.property_states}
    for pid in sorted(set(b_props) | set(a_props)):
        bp, ap = b_props.get(pid), a_props.get(pid)
        if bp is None:
            key = f"PROPERTY:{pid}:property"
            add_change(
                scope="PROPERTY", object_type="PROPERTY", object_id=pid, domain="PROPERTY",
                field_path="property", before_value=None, after_value=asdict(ap),
                classification="ADDED",
                cause=_cause_for(key, registry=delta_registry, cause_overrides=cause_overrides),
                cause_key=key, evidence_fingerprints=(ap.projection_fingerprint,),
            )
            continue
        if ap is None:
            key = f"PROPERTY:{pid}:property"
            add_change(
                scope="PROPERTY", object_type="PROPERTY", object_id=pid, domain="PROPERTY",
                field_path="property", before_value=asdict(bp), after_value=None,
                classification="REMOVED",
                cause=_cause_for(key, registry=delta_registry, cause_overrides=cause_overrides),
                cause_key=key, evidence_fingerprints=(bp.projection_fingerprint,),
            )
            continue
        for field_path, domain in _PROPERTY_FIELDS:
            b = getattr(bp, field_path)
            a = getattr(ap, field_path)
            classification = _classify_value(field_path, b, a)
            key = f"PROPERTY:{pid}:{field_path}"
            add_change(
                scope="PROPERTY", object_type="PROPERTY", object_id=pid, domain=domain,
                field_path=field_path, before_value=b, after_value=a,
                classification=classification,
                cause=_cause_for(key, registry=delta_registry, cause_overrides=cause_overrides),
                cause_key=key,
                evidence_fingerprints=(bp.projection_fingerprint, ap.projection_fingerprint),
            )

    for kind in ("source", "policy", "runtime"):
        bm, am = _manifest_map(before, kind), _manifest_map(after, kind)
        domain = _manifest_domain(kind)
        for identity in sorted(set(bm) | set(am)):
            be, ae = bm.get(identity), am.get(identity)
            object_id = f"{identity[0]}:{identity[1]}"
            key = f"{domain}:{object_id}:fingerprint"
            inferred = _manifest_inferred_cause(
                kind=kind, before_entry=be, after_entry=ae, before=before
            )
            cause = _cause_for(
                key, registry=delta_registry, cause_overrides=cause_overrides, inferred=inferred
            )
            if be is None:
                classification = "BECAME_KNOWN" if inferred and inferred.cause == "NEWLY_OBSERVED_FACT" else "ADDED"
                bval, aval = None, asdict(ae)
                exact_effective = ae.effective_at
                evidence = (ae.fingerprint,)
            elif ae is None:
                classification = "REMOVED"
                bval, aval = asdict(be), None
                exact_effective = None
                evidence = (be.fingerprint,)
            else:
                classification = "UNCHANGED" if be == ae else "MODIFIED"
                bval, aval = asdict(be), asdict(ae)
                exact_effective = ae.effective_at if classification != "UNCHANGED" else be.effective_at
                evidence = (be.fingerprint, ae.fingerprint)
            add_change(
                scope="MANIFEST", object_type=f"{domain}_MANIFEST_ENTRY", object_id=object_id,
                domain=domain, field_path="manifest_entry",
                before_value=bval, after_value=aval, classification=classification,
                cause=cause, cause_key=key, evidence_fingerprints=evidence,
                exact_effective_at=exact_effective,
            )

    changes_tuple = tuple(sorted(changes, key=lambda x: (x.scope, x.object_type, x.object_id, x.field_path)))
    edges = tuple(
        sorted(
            (edge for change in changes_tuple if (edge := _impact_edge(change, registry=delta_registry)) is not None),
            key=lambda x: (x.affected_object_type, x.affected_object_id, x.source_change_fingerprint),
        )
    )
    materialities = [x.materiality for x in changes_tuple if x.classification != "UNCHANGED"]
    highest = max(materialities, key=lambda x: _MATERIALITY_ORDER[x]) if materialities else "INFORMATIONAL"
    lineage = tuple(sorted({
        before.semantic_hash,
        before.record_hash,
        after.semantic_hash,
        after.record_hash,
        before.m12_release_certification_root,
    } | {fp for x in changes_tuple for fp in x.evidence_fingerprints}))
    fingerprint_payload = {
        "delta_id": delta_id,
        "community_id": before.community_id,
        "before_snapshot_id": before.snapshot_id,
        "after_snapshot_id": after.snapshot_id,
        "before_snapshot_semantic_hash": before.semantic_hash,
        "after_snapshot_semantic_hash": after.semantic_hash,
        "before_observation_time": before.observation_time,
        "after_observation_time": after.observation_time,
        "detected_at": detected_at,
        "materiality_rules_version": delta_registry["materiality"]["version"],
        "changes": tuple(asdict(x) for x in changes_tuple),
        "impact_edges": tuple(asdict(x) for x in edges),
        "highest_materiality": highest,
        "lineage_fingerprints": lineage,
        "certification_state": "DRAFT",
        "reproducible": True,
    }
    return CommunityDelta(
        delta_id=delta_id,
        community_id=before.community_id,
        before_snapshot_id=before.snapshot_id,
        after_snapshot_id=after.snapshot_id,
        before_snapshot_semantic_hash=before.semantic_hash,
        after_snapshot_semantic_hash=after.semantic_hash,
        before_observation_time=before.observation_time,
        after_observation_time=after.observation_time,
        detected_at=detected_at,
        materiality_rules_version=delta_registry["materiality"]["version"],
        changes=changes_tuple,
        impact_edges=edges,
        highest_materiality=highest,
        lineage_fingerprints=lineage,
        certification_state="DRAFT",
        reproducible=True,
        delta_fingerprint=_hash(fingerprint_payload),
    )


def validate_delta_replay(delta: CommunityDelta) -> bool:
    payload = {
        "delta_id": delta.delta_id,
        "community_id": delta.community_id,
        "before_snapshot_id": delta.before_snapshot_id,
        "after_snapshot_id": delta.after_snapshot_id,
        "before_snapshot_semantic_hash": delta.before_snapshot_semantic_hash,
        "after_snapshot_semantic_hash": delta.after_snapshot_semantic_hash,
        "before_observation_time": delta.before_observation_time,
        "after_observation_time": delta.after_observation_time,
        "detected_at": delta.detected_at,
        "materiality_rules_version": delta.materiality_rules_version,
        "changes": tuple(asdict(x) for x in delta.changes),
        "impact_edges": tuple(asdict(x) for x in delta.impact_edges),
        "highest_materiality": delta.highest_materiality,
        "lineage_fingerprints": delta.lineage_fingerprints,
        "certification_state": "DRAFT",
        "reproducible": True,
    }
    return _hash(payload) == delta.delta_fingerprint


def certify_delta(delta: CommunityDelta) -> CommunityDelta:
    if delta.certification_state != "DRAFT":
        raise ValueError("only DRAFT delta may be certified")
    if not validate_delta_replay(delta):
        raise ValueError("delta is nonreproducible")
    if any(x.classification == "NOT_COMPARABLE" for x in delta.changes):
        raise ValueError("NOT_COMPARABLE change blocks delta certification")
    return replace(delta, certification_state="CERTIFIED")
