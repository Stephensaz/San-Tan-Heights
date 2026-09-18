from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from datetime import datetime
import hashlib
import json
from pathlib import Path
from typing import Iterable, Mapping, Sequence

import yaml

from src.community_temporal_state.delta import CommunityDelta, validate_delta_replay
from src.community_temporal_state.impact_refresh import (
    SelectiveRefreshPlan,
    SelectiveRefreshResult,
    validate_refresh_plan_replay,
    validate_refresh_result_replay,
)
from src.community_temporal_state.snapshot import (
    CommunityStateSnapshot,
    validate_snapshot_replay,
)


UNKNOWN = "UNKNOWN"


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
    if len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
        raise ValueError(f"{label} must be lowercase sha256")


def load_temporal_history_registry(path: str | Path) -> dict:
    data = yaml.safe_load(Path(path).read_text())
    if data.get("status") != "FROZEN" or data.get("ticket") != "M13-004":
        raise ValueError("M13-004 temporal history registry must be FROZEN")
    if data.get("temporal_history_registry_id") != "STH-M13-004-TEMPORAL-HISTORY-v1.0":
        raise ValueError("unexpected M13-004 temporal history registry id")
    return data


@dataclass(frozen=True)
class TemporalLedgerEntry:
    entry_id: str
    community_id: str
    entry_type: str
    scope: str
    scope_id: str
    fact_key: str
    fact_value: object
    valid_from: str
    valid_to: str | None
    known_at: str
    recorded_at: str
    truth_state: str
    source_fingerprints: tuple[str, ...]
    previous_entry_fingerprint: str | None
    originating_delta_fingerprint: str | None
    refresh_plan_fingerprint: str | None
    refresh_result_fingerprint: str | None
    evidence_fingerprints: tuple[str, ...]
    limitations: tuple[str, ...]
    entry_fingerprint: str


@dataclass(frozen=True)
class TemporalLedger:
    ledger_id: str
    community_id: str
    entries: tuple[TemporalLedgerEntry, ...]
    ledger_fingerprint: str


@dataclass(frozen=True)
class HistoryView:
    mode: str
    community_id: str
    scope: str
    scope_id: str
    as_of_valid_time: str | None
    as_of_knowledge_time: str | None
    entries: tuple[TemporalLedgerEntry, ...]
    view_fingerprint: str


def make_temporal_entry(
    *,
    entry_id: str,
    community_id: str,
    entry_type: str,
    scope: str,
    scope_id: str,
    fact_key: str,
    fact_value: object,
    valid_from: str,
    known_at: str,
    recorded_at: str,
    registry: Mapping[str, object],
    valid_to: str | None = None,
    truth_state: str = "ASSERTED",
    source_fingerprints: Sequence[str] = (),
    previous_entry_fingerprint: str | None = None,
    originating_delta_fingerprint: str | None = None,
    refresh_plan_fingerprint: str | None = None,
    refresh_result_fingerprint: str | None = None,
    evidence_fingerprints: Sequence[str] = (),
    limitations: Sequence[str] = (),
) -> TemporalLedgerEntry:
    if not all(x.strip() for x in (entry_id, community_id, scope_id, fact_key)):
        raise ValueError("entry identity, community, scope_id, and fact_key are required")
    if entry_type not in set(registry["entry_types"]):
        raise ValueError("unsupported temporal entry type")
    if scope not in set(registry["scopes"]):
        raise ValueError("unsupported temporal entry scope")
    if truth_state not in set(registry["truth_states"]):
        raise ValueError("unsupported truth state")
    valid_dt = _parse_ts(valid_from, "valid_from")
    known_dt = _parse_ts(known_at, "known_at")
    recorded_dt = _parse_ts(recorded_at, "recorded_at")
    if recorded_dt < known_dt:
        raise ValueError("recorded_at cannot precede known_at")
    if valid_to is not None:
        valid_to_dt = _parse_ts(valid_to, "valid_to")
        if valid_to_dt < valid_dt:
            raise ValueError("valid_to cannot precede valid_from")
    fps = tuple(sorted(set(source_fingerprints)))
    evidence = tuple(sorted(set(evidence_fingerprints)))
    for fp in (*fps, *evidence):
        _validate_fp(fp, "temporal lineage fingerprint")
    for label, fp in (
        ("previous entry fingerprint", previous_entry_fingerprint),
        ("originating delta fingerprint", originating_delta_fingerprint),
        ("refresh plan fingerprint", refresh_plan_fingerprint),
        ("refresh result fingerprint", refresh_result_fingerprint),
    ):
        if fp is not None:
            _validate_fp(fp, label)
    if entry_type == "CORRECTION" and previous_entry_fingerprint is None:
        raise ValueError("correction requires previous entry fingerprint")
    payload = {
        "entry_id": entry_id,
        "community_id": community_id,
        "entry_type": entry_type,
        "scope": scope,
        "scope_id": scope_id,
        "fact_key": fact_key,
        "fact_value": fact_value,
        "valid_from": valid_from,
        "valid_to": valid_to,
        "known_at": known_at,
        "recorded_at": recorded_at,
        "truth_state": truth_state,
        "source_fingerprints": fps,
        "previous_entry_fingerprint": previous_entry_fingerprint,
        "originating_delta_fingerprint": originating_delta_fingerprint,
        "refresh_plan_fingerprint": refresh_plan_fingerprint,
        "refresh_result_fingerprint": refresh_result_fingerprint,
        "evidence_fingerprints": evidence,
        "limitations": tuple(sorted(set(limitations))),
    }
    return TemporalLedgerEntry(**payload, entry_fingerprint=_hash(payload))


def _entry_sort_key(entry: TemporalLedgerEntry) -> tuple:
    return (entry.valid_from, entry.known_at, entry.entry_id, entry.entry_fingerprint)


def build_temporal_ledger(
    *,
    ledger_id: str,
    community_id: str,
    entries: Sequence[TemporalLedgerEntry],
) -> TemporalLedger:
    if not ledger_id.strip() or not community_id.strip():
        raise ValueError("ledger_id and community_id required")
    if any(x.community_id != community_id for x in entries):
        raise ValueError("ledger community mismatch")
    if len({x.entry_id for x in entries}) != len(entries):
        raise ValueError("duplicate temporal entry ids prohibited")
    ordered = tuple(sorted(entries, key=_entry_sort_key))
    payload = {
        "ledger_id": ledger_id,
        "community_id": community_id,
        "entries": tuple(asdict(x) for x in ordered),
    }
    return TemporalLedger(
        ledger_id=ledger_id,
        community_id=community_id,
        entries=ordered,
        ledger_fingerprint=_hash(payload),
    )


def append_entries(
    ledger: TemporalLedger,
    *,
    new_entries: Sequence[TemporalLedgerEntry],
) -> TemporalLedger:
    existing_ids = {x.entry_id for x in ledger.entries}
    existing_fps = {x.entry_fingerprint for x in ledger.entries}
    if any(x.entry_id in existing_ids for x in new_entries):
        raise ValueError("append-only ledger rejects duplicate entry ids")
    for entry in new_entries:
        if entry.community_id != ledger.community_id:
            raise ValueError("ledger community mismatch")
        if entry.previous_entry_fingerprint is not None and entry.previous_entry_fingerprint not in existing_fps:
            raise ValueError("correction/supersession link must reference existing immutable history")
    return build_temporal_ledger(
        ledger_id=ledger.ledger_id,
        community_id=ledger.community_id,
        entries=ledger.entries + tuple(new_entries),
    )


def validate_ledger_replay(ledger: TemporalLedger) -> bool:
    payload = {
        "ledger_id": ledger.ledger_id,
        "community_id": ledger.community_id,
        "entries": tuple(asdict(x) for x in ledger.entries),
    }
    return _hash(payload) == ledger.ledger_fingerprint


def snapshot_entries(
    snapshot: CommunityStateSnapshot,
    *,
    recorded_at: str,
    registry: Mapping[str, object],
) -> tuple[TemporalLedgerEntry, ...]:
    if snapshot.certification_state != "CERTIFIED" or not validate_snapshot_replay(snapshot):
        raise ValueError("M13-004 requires certified reproducible M13-001 snapshot")
    out: list[TemporalLedgerEntry] = []
    for prop in snapshot.property_states:
        out.append(make_temporal_entry(
            entry_id=f"SNAP:{snapshot.snapshot_id}:{prop.property_id}",
            community_id=snapshot.community_id,
            entry_type="SNAPSHOT",
            scope="PROPERTY",
            scope_id=prop.property_id,
            fact_key="property_projection",
            fact_value=asdict(prop),
            valid_from=snapshot.observation_time,
            known_at=snapshot.knowledge_cutoff,
            recorded_at=recorded_at,
            registry=registry,
            source_fingerprints=(snapshot.semantic_hash, snapshot.record_hash, prop.projection_fingerprint),
            evidence_fingerprints=(snapshot.semantic_hash, prop.projection_fingerprint),
            limitations=snapshot.blocking_conditions,
        ))
    out.append(make_temporal_entry(
        entry_id=f"SNAP:{snapshot.snapshot_id}:COMMUNITY",
        community_id=snapshot.community_id,
        entry_type="SNAPSHOT",
        scope="COMMUNITY",
        scope_id=snapshot.community_id,
        fact_key="community_snapshot",
        fact_value={
            "snapshot_id": snapshot.snapshot_id,
            "corpus_property_ids": snapshot.corpus_property_ids,
            "freshness_state": snapshot.freshness_state,
            "exclusions": snapshot.exclusions,
            "conflicts": snapshot.conflicts,
        },
        valid_from=snapshot.observation_time,
        known_at=snapshot.knowledge_cutoff,
        recorded_at=recorded_at,
        registry=registry,
        source_fingerprints=(snapshot.semantic_hash, snapshot.record_hash),
        evidence_fingerprints=(snapshot.semantic_hash,),
        limitations=snapshot.blocking_conditions,
    ))
    return tuple(out)


def delta_entries(
    delta: CommunityDelta,
    *,
    recorded_at: str,
    registry: Mapping[str, object],
) -> tuple[TemporalLedgerEntry, ...]:
    if delta.certification_state != "CERTIFIED" or not validate_delta_replay(delta):
        raise ValueError("M13-004 requires certified reproducible M13-002 delta")
    out: list[TemporalLedgerEntry] = []
    for change in delta.changes:
        if change.classification == "UNCHANGED":
            continue
        valid_from = change.effective_at if change.effective_at != UNKNOWN else change.first_observed_at
        limits = ("EFFECTIVE_TIME_UNKNOWN_USED_FIRST_OBSERVED",) if change.effective_at == UNKNOWN else ()
        out.append(make_temporal_entry(
            entry_id=f"DELTA:{delta.delta_id}:{change.change_id}",
            community_id=delta.community_id,
            entry_type="DELTA",
            scope=change.scope if change.scope in {"PROPERTY", "COMMUNITY", "MANIFEST"} else "INTELLIGENCE",
            scope_id=change.object_id,
            fact_key=change.field_path,
            fact_value={
                "classification": change.classification,
                "before": change.before_value,
                "after": change.after_value,
                "cause": change.change_cause,
                "causation_basis": change.causation_basis,
            },
            valid_from=valid_from,
            known_at=change.detected_at,
            recorded_at=recorded_at,
            registry=registry,
            originating_delta_fingerprint=delta.delta_fingerprint,
            source_fingerprints=(delta.delta_fingerprint, change.change_fingerprint),
            evidence_fingerprints=change.evidence_fingerprints,
            limitations=limits,
        ))
    return tuple(out)


def refresh_entries(
    *,
    community_id: str,
    plan: SelectiveRefreshPlan,
    result: SelectiveRefreshResult,
    known_at: str,
    recorded_at: str,
    registry: Mapping[str, object],
) -> tuple[TemporalLedgerEntry, ...]:
    if not validate_refresh_plan_replay(plan) or not validate_refresh_result_replay(result):
        raise ValueError("M13-004 requires reproducible M13-003 refresh state")
    if result.plan_fingerprint != plan.plan_fingerprint:
        raise ValueError("refresh result/plan lineage mismatch")
    out: list[TemporalLedgerEntry] = []
    by_id = {x.artifact_id: x for x in result.records}
    for decision in plan.decisions:
        out.append(make_temporal_entry(
            entry_id=f"REFRESH:{plan.plan_id}:{decision.artifact_id}",
            community_id=community_id,
            entry_type="REFRESH_RESULT",
            scope="INTELLIGENCE",
            scope_id=decision.scope_id,
            fact_key=decision.artifact_type,
            fact_value={
                "decision": decision.decision,
                "reason_codes": decision.reason_codes,
                "artifact_id": decision.artifact_id,
                "record_fingerprint": by_id[decision.artifact_id].record_fingerprint,
            },
            valid_from=known_at,
            known_at=known_at,
            recorded_at=recorded_at,
            registry=registry,
            originating_delta_fingerprint=plan.delta_fingerprint,
            refresh_plan_fingerprint=plan.plan_fingerprint,
            refresh_result_fingerprint=result.result_fingerprint,
            source_fingerprints=(
                plan.delta_fingerprint,
                plan.plan_fingerprint,
                result.result_fingerprint,
                decision.decision_fingerprint,
            ),
            evidence_fingerprints=decision.source_change_fingerprints,
        ))
    return tuple(out)


def append_correction(
    ledger: TemporalLedger,
    *,
    correction_id: str,
    target_entry_fingerprint: str,
    corrected_value: object,
    valid_from: str,
    known_at: str,
    recorded_at: str,
    registry: Mapping[str, object],
    evidence_fingerprints: Sequence[str],
    limitations: Sequence[str] = (),
) -> TemporalLedger:
    matches = [x for x in ledger.entries if x.entry_fingerprint == target_entry_fingerprint]
    if len(matches) != 1:
        raise ValueError("correction target must resolve exactly once")
    target = matches[0]
    correction = make_temporal_entry(
        entry_id=correction_id,
        community_id=ledger.community_id,
        entry_type="CORRECTION",
        scope=target.scope,
        scope_id=target.scope_id,
        fact_key=target.fact_key,
        fact_value=corrected_value,
        valid_from=valid_from,
        known_at=known_at,
        recorded_at=recorded_at,
        registry=registry,
        truth_state="CORRECTED",
        source_fingerprints=(target.entry_fingerprint,),
        previous_entry_fingerprint=target.entry_fingerprint,
        evidence_fingerprints=evidence_fingerprints,
        limitations=limitations,
    )
    return append_entries(ledger, new_entries=(correction,))


def historical_view(
    ledger: TemporalLedger,
    *,
    mode: str,
    scope: str,
    scope_id: str,
    registry: Mapping[str, object],
    as_of_valid_time: str | None = None,
    as_of_knowledge_time: str | None = None,
) -> HistoryView:
    if mode not in set(registry["query_modes"]):
        raise ValueError("unsupported historical query mode")
    if not validate_ledger_replay(ledger):
        raise ValueError("temporal ledger is nonreproducible")
    rows = [x for x in ledger.entries if x.scope == scope and x.scope_id == scope_id]
    valid_cutoff = _parse_ts(as_of_valid_time, "as_of_valid_time") if as_of_valid_time else None
    knowledge_cutoff = _parse_ts(as_of_knowledge_time, "as_of_knowledge_time") if as_of_knowledge_time else None

    if mode in {"TRUE_THEN", "KNOWN_THEN"} and valid_cutoff is None:
        raise ValueError(f"{mode} requires as_of_valid_time")
    if mode == "KNOWN_THEN" and knowledge_cutoff is None:
        raise ValueError("KNOWN_THEN requires as_of_knowledge_time")

    def visible(entry: TemporalLedgerEntry) -> bool:
        valid = _parse_ts(entry.valid_from, "entry valid_from")
        known = _parse_ts(entry.known_at, "entry known_at")
        if mode == "TRUE_NOW":
            return True
        if mode == "TRUE_THEN":
            return valid <= valid_cutoff
        if mode == "KNOWN_THEN":
            return valid <= valid_cutoff and known <= knowledge_cutoff
        if mode == "KNOWN_NOW":
            return True
        return False

    visible_rows = tuple(sorted((x for x in rows if visible(x)), key=_entry_sort_key))
    payload = {
        "mode": mode,
        "community_id": ledger.community_id,
        "scope": scope,
        "scope_id": scope_id,
        "as_of_valid_time": as_of_valid_time,
        "as_of_knowledge_time": as_of_knowledge_time,
        "entries": tuple(asdict(x) for x in visible_rows),
    }
    return HistoryView(**payload, view_fingerprint=_hash(payload))


def community_history_summary(ledger: TemporalLedger) -> dict:
    if not validate_ledger_replay(ledger):
        raise ValueError("temporal ledger is nonreproducible")
    by_type: dict[str, int] = {}
    by_scope: dict[str, int] = {}
    for entry in ledger.entries:
        by_type[entry.entry_type] = by_type.get(entry.entry_type, 0) + 1
        by_scope[entry.scope] = by_scope.get(entry.scope, 0) + 1
    payload = {
        "community_id": ledger.community_id,
        "entry_count": len(ledger.entries),
        "by_entry_type": dict(sorted(by_type.items())),
        "by_scope": dict(sorted(by_scope.items())),
        "ledger_fingerprint": ledger.ledger_fingerprint,
    }
    return {**payload, "summary_fingerprint": _hash(payload)}
