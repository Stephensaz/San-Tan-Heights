from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
import hashlib
import json
from pathlib import Path
from typing import Mapping, Sequence

import yaml

from src.community_temporal_state.history import TemporalLedger, TemporalLedgerEntry, validate_ledger_replay
from src.community_temporal_state.scenario_baseline import CertifiedScenarioBaseline


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


def load_scenario_evidence_registry(path: str | Path) -> dict:
    data = yaml.safe_load(Path(path).read_text())
    if data.get("status") != "FROZEN" or data.get("ticket") != "M13-006C":
        raise ValueError("M13-006C scenario evidence registry must be FROZEN")
    if data.get("scenario_evidence_registry_id") != "STH-M13-006C-SCENARIO-EVIDENCE-v1.0":
        raise ValueError("unexpected M13-006C scenario evidence registry id")
    return data


@dataclass(frozen=True)
class ScenarioEvidenceQuery:
    query_id: str
    scenario_context_fingerprint: str
    community_id: str
    subject_id: str
    scopes: tuple[str, ...]
    fact_keys: tuple[str, ...]
    valid_from: str
    valid_to: str
    knowledge_cutoff: str
    include_subject_history: bool
    include_community_history: bool
    query_fingerprint: str


@dataclass(frozen=True)
class ScenarioEvidenceRecord:
    entry_id: str
    entry_fingerprint: str
    state: str
    reason_codes: tuple[str, ...]
    scope: str
    scope_id: str
    fact_key: str
    fact_value: object
    valid_from: str
    valid_to: str | None
    known_at: str
    truth_state: str
    source_fingerprints: tuple[str, ...]
    evidence_fingerprints: tuple[str, ...]
    previous_entry_fingerprint: str | None
    limitations: tuple[str, ...]
    record_fingerprint: str


@dataclass(frozen=True)
class ScenarioEvidenceSet:
    evidence_set_id: str
    scenario_id: str
    scenario_context_fingerprint: str
    temporal_ledger_fingerprint: str
    query_fingerprint: str
    included: tuple[ScenarioEvidenceRecord, ...]
    excluded: tuple[ScenarioEvidenceRecord, ...]
    source_fingerprints: tuple[str, ...]
    evidence_fingerprints: tuple[str, ...]
    unknowns: tuple[str, ...]
    limitations: tuple[str, ...]
    evidence_set_fingerprint: str


def build_scenario_evidence_query(
    *,
    query_id: str,
    context: CertifiedScenarioBaseline,
    scopes: Sequence[str],
    fact_keys: Sequence[str],
    valid_from: str,
    valid_to: str,
    knowledge_cutoff: str,
    registry: Mapping[str, object],
    include_subject_history: bool = True,
    include_community_history: bool = True,
) -> ScenarioEvidenceQuery:
    if not query_id.strip():
        raise ValueError("query_id required")
    _validate_fp(context.context_fingerprint, "scenario context fingerprint")
    allowed_scopes = set(registry["allowed_scopes"])
    scope_rows = tuple(sorted(set(x.strip() for x in scopes if x.strip())))
    if not scope_rows or not set(scope_rows).issubset(allowed_scopes):
        raise ValueError("query scopes must be explicit and governed")
    keys = tuple(sorted(set(x.strip() for x in fact_keys if x.strip())))
    if registry["policy"]["require_explicit_fact_keys"] and not keys:
        raise ValueError("explicit fact keys required")
    start = _parse_ts(valid_from, "valid_from")
    end = _parse_ts(valid_to, "valid_to")
    cutoff = _parse_ts(knowledge_cutoff, "knowledge_cutoff")
    if end < start:
        raise ValueError("valid_to cannot precede valid_from")
    if cutoff < start:
        raise ValueError("knowledge_cutoff cannot precede valid_from")
    payload = {
        "query_id": query_id,
        "scenario_context_fingerprint": context.context_fingerprint,
        "community_id": context.community_id,
        "subject_id": context.subject_id,
        "scopes": scope_rows,
        "fact_keys": keys,
        "valid_from": valid_from,
        "valid_to": valid_to,
        "knowledge_cutoff": knowledge_cutoff,
        "include_subject_history": bool(include_subject_history),
        "include_community_history": bool(include_community_history),
    }
    return ScenarioEvidenceQuery(**payload, query_fingerprint=_hash(payload))


def _entry_decision(
    entry: TemporalLedgerEntry,
    *,
    query: ScenarioEvidenceQuery,
    registry: Mapping[str, object],
) -> tuple[str, tuple[str, ...]]:
    reasons: list[str] = []
    start = _parse_ts(query.valid_from, "query valid_from")
    end = _parse_ts(query.valid_to, "query valid_to")
    cutoff = _parse_ts(query.knowledge_cutoff, "query knowledge cutoff")
    valid = _parse_ts(entry.valid_from, "entry valid_from")
    known = _parse_ts(entry.known_at, "entry known_at")

    if entry.community_id != query.community_id:
        reasons.append("COMMUNITY_MISMATCH")
    if entry.scope not in query.scopes:
        reasons.append("SCOPE_NOT_REQUESTED")
    if entry.fact_key not in query.fact_keys:
        reasons.append("FACT_KEY_NOT_REQUESTED")
    if valid < start or valid > end:
        reasons.append("OUTSIDE_VALID_TIME_WINDOW")
    if known > cutoff:
        reasons.append("KNOWN_AFTER_CUTOFF")
    if entry.scope == "PROPERTY":
        if not query.include_subject_history:
            reasons.append("SUBJECT_HISTORY_DISABLED")
        elif entry.scope_id != query.subject_id:
            reasons.append("SUBJECT_MISMATCH")
    if entry.scope == "COMMUNITY" and not query.include_community_history:
        reasons.append("COMMUNITY_HISTORY_DISABLED")
    if entry.truth_state not in set(registry["allowed_truth_states"]):
        reasons.append("TRUTH_STATE_NOT_ALLOWED")
    if registry["policy"]["require_source_lineage"] and not entry.source_fingerprints:
        reasons.append("SOURCE_LINEAGE_MISSING")
    state = "INCLUDED" if not reasons else "EXCLUDED"
    return state, tuple(sorted(set(reasons or ["GOVERNED_QUERY_MATCH"])))


def _make_record(entry: TemporalLedgerEntry, state: str, reasons: tuple[str, ...]) -> ScenarioEvidenceRecord:
    payload = {
        "entry_id": entry.entry_id,
        "entry_fingerprint": entry.entry_fingerprint,
        "state": state,
        "reason_codes": reasons,
        "scope": entry.scope,
        "scope_id": entry.scope_id,
        "fact_key": entry.fact_key,
        "fact_value": entry.fact_value,
        "valid_from": entry.valid_from,
        "valid_to": entry.valid_to,
        "known_at": entry.known_at,
        "truth_state": entry.truth_state,
        "source_fingerprints": tuple(entry.source_fingerprints),
        "evidence_fingerprints": tuple(entry.evidence_fingerprints),
        "previous_entry_fingerprint": entry.previous_entry_fingerprint,
        "limitations": tuple(entry.limitations),
    }
    return ScenarioEvidenceRecord(**payload, record_fingerprint=_hash(payload))


def retrieve_scenario_evidence(
    *,
    evidence_set_id: str,
    context: CertifiedScenarioBaseline,
    ledger: TemporalLedger,
    query: ScenarioEvidenceQuery,
    registry: Mapping[str, object],
    additional_unknowns: Sequence[str] = (),
    additional_limitations: Sequence[str] = (),
) -> ScenarioEvidenceSet:
    if not evidence_set_id.strip():
        raise ValueError("evidence_set_id required")
    if not validate_ledger_replay(ledger):
        raise ValueError("reproducible temporal ledger required")
    if ledger.community_id != context.community_id or query.community_id != context.community_id:
        raise ValueError("community lineage mismatch")
    if query.scenario_context_fingerprint != context.context_fingerprint:
        raise ValueError("scenario context fingerprint mismatch")
    _validate_fp(context.context_fingerprint, "scenario context fingerprint")
    _validate_fp(ledger.ledger_fingerprint, "temporal ledger fingerprint")

    included: list[ScenarioEvidenceRecord] = []
    excluded: list[ScenarioEvidenceRecord] = []
    for entry in ledger.entries:
        state, reasons = _entry_decision(entry, query=query, registry=registry)
        record = _make_record(entry, state, reasons)
        (included if state == "INCLUDED" else excluded).append(record)

    included_rows = tuple(sorted(included, key=lambda x: (x.valid_from, x.known_at, x.entry_id, x.entry_fingerprint)))
    excluded_rows = tuple(sorted(excluded, key=lambda x: (x.valid_from, x.known_at, x.entry_id, x.entry_fingerprint)))
    source_fps = tuple(sorted({fp for row in included_rows for fp in row.source_fingerprints}))
    evidence_fps = tuple(sorted({fp for row in included_rows for fp in row.evidence_fingerprints}))
    limits = tuple(sorted(set(
        [x.strip() for x in additional_limitations if x.strip()]
        + [limit for row in included_rows for limit in row.limitations if limit]
        + ["Historical evidence is descriptive and does not predict future outcomes."]
    )))
    unknowns = set(x.strip() for x in additional_unknowns if x.strip())
    if not included_rows:
        unknowns.add("NO_HISTORICAL_EVIDENCE_MATCHED_GOVERNED_QUERY")

    payload = {
        "evidence_set_id": evidence_set_id,
        "scenario_id": context.scenario_id,
        "scenario_context_fingerprint": context.context_fingerprint,
        "temporal_ledger_fingerprint": ledger.ledger_fingerprint,
        "query_fingerprint": query.query_fingerprint,
        "included": tuple(asdict(x) for x in included_rows),
        "excluded": tuple(asdict(x) for x in excluded_rows),
        "source_fingerprints": source_fps,
        "evidence_fingerprints": evidence_fps,
        "unknowns": tuple(sorted(unknowns)),
        "limitations": limits,
    }
    return ScenarioEvidenceSet(
        evidence_set_id=evidence_set_id,
        scenario_id=context.scenario_id,
        scenario_context_fingerprint=context.context_fingerprint,
        temporal_ledger_fingerprint=ledger.ledger_fingerprint,
        query_fingerprint=query.query_fingerprint,
        included=included_rows,
        excluded=excluded_rows,
        source_fingerprints=source_fps,
        evidence_fingerprints=evidence_fps,
        unknowns=payload["unknowns"],
        limitations=limits,
        evidence_set_fingerprint=_hash(payload),
    )


def validate_scenario_evidence_replay(
    evidence_set: ScenarioEvidenceSet,
    *,
    context: CertifiedScenarioBaseline,
    ledger: TemporalLedger,
    query: ScenarioEvidenceQuery,
    registry: Mapping[str, object],
) -> bool:
    replay = retrieve_scenario_evidence(
        evidence_set_id=evidence_set.evidence_set_id,
        context=context,
        ledger=ledger,
        query=query,
        registry=registry,
        additional_unknowns=tuple(
            x for x in evidence_set.unknowns
            if x != "NO_HISTORICAL_EVIDENCE_MATCHED_GOVERNED_QUERY"
        ),
        additional_limitations=tuple(
            x for x in evidence_set.limitations
            if x != "Historical evidence is descriptive and does not predict future outcomes."
            and not any(x in row.limitations for row in evidence_set.included)
        ),
    )
    return replay == evidence_set
