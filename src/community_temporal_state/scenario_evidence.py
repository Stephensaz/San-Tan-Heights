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


def _parse_ts(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("timestamp must be timezone-aware")
    return parsed


def load_historical_evidence_registry(path: str | Path) -> dict:
    data = yaml.safe_load(Path(path).read_text())
    if data.get("status") != "FROZEN" or data.get("ticket") != "M13-006C":
        raise ValueError("M13-006C historical evidence registry must be FROZEN")
    if data.get("historical_evidence_registry_id") != "STH-M13-006C-HISTORICAL-EVIDENCE-v1.0":
        raise ValueError("unexpected M13-006C historical evidence registry id")
    return data


@dataclass(frozen=True)
class HistoricalEvidenceRule:
    rule_id: str
    scope: str
    fact_keys: tuple[str, ...]
    truth_states: tuple[str, ...]
    valid_from: str | None
    valid_to: str | None
    known_by: str | None
    minimum_items: int
    maximum_items: int
    rule_fingerprint: str


@dataclass(frozen=True)
class HistoricalEvidenceItem:
    entry_id: str
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
    limitations: tuple[str, ...]
    entry_fingerprint: str
    item_fingerprint: str


@dataclass(frozen=True)
class HistoricalEvidenceSet:
    evidence_set_id: str
    scenario_id: str
    certified_context_fingerprint: str
    temporal_ledger_fingerprint: str
    rule_fingerprint: str
    items: tuple[HistoricalEvidenceItem, ...]
    coverage_state: str
    requested_fact_keys: tuple[str, ...]
    matched_fact_keys: tuple[str, ...]
    missing_fact_keys: tuple[str, ...]
    limitations: tuple[str, ...]
    evidence_set_fingerprint: str


def make_historical_evidence_rule(
    *,
    rule_id: str,
    scope: str,
    fact_keys: Sequence[str],
    truth_states: Sequence[str],
    minimum_items: int,
    maximum_items: int,
    valid_from: str | None = None,
    valid_to: str | None = None,
    known_by: str | None = None,
) -> HistoricalEvidenceRule:
    if not rule_id.strip() or not scope.strip():
        raise ValueError("rule id and scope required")
    if minimum_items < 0 or maximum_items < 1 or minimum_items > maximum_items:
        raise ValueError("invalid evidence item bounds")
    for value in (valid_from, valid_to, known_by):
        if value is not None:
            _parse_ts(value)
    if valid_from and valid_to and _parse_ts(valid_to) < _parse_ts(valid_from):
        raise ValueError("valid_to cannot precede valid_from")
    payload = {
        "rule_id": rule_id,
        "scope": scope,
        "fact_keys": tuple(sorted(set(x.strip() for x in fact_keys if x.strip()))),
        "truth_states": tuple(sorted(set(x.strip() for x in truth_states if x.strip()))),
        "valid_from": valid_from,
        "valid_to": valid_to,
        "known_by": known_by,
        "minimum_items": minimum_items,
        "maximum_items": maximum_items,
    }
    return HistoricalEvidenceRule(**payload, rule_fingerprint=_hash(payload))


def _matches(entry: TemporalLedgerEntry, rule: HistoricalEvidenceRule) -> bool:
    if entry.scope != rule.scope:
        return False
    if rule.fact_keys and entry.fact_key not in set(rule.fact_keys):
        return False
    if rule.truth_states and entry.truth_state not in set(rule.truth_states):
        return False
    if rule.valid_from is not None and _parse_ts(entry.valid_from) < _parse_ts(rule.valid_from):
        return False
    if rule.valid_to is not None and _parse_ts(entry.valid_from) > _parse_ts(rule.valid_to):
        return False
    if rule.known_by is not None and _parse_ts(entry.known_at) > _parse_ts(rule.known_by):
        return False
    return True


def _to_item(entry: TemporalLedgerEntry) -> HistoricalEvidenceItem:
    payload = {
        "entry_id": entry.entry_id,
        "scope": entry.scope,
        "scope_id": entry.scope_id,
        "fact_key": entry.fact_key,
        "fact_value": entry.fact_value,
        "valid_from": entry.valid_from,
        "valid_to": entry.valid_to,
        "known_at": entry.known_at,
        "truth_state": entry.truth_state,
        "source_fingerprints": entry.source_fingerprints,
        "evidence_fingerprints": entry.evidence_fingerprints,
        "limitations": entry.limitations,
        "entry_fingerprint": entry.entry_fingerprint,
    }
    return HistoricalEvidenceItem(**payload, item_fingerprint=_hash(payload))


def retrieve_historical_evidence(
    *,
    evidence_set_id: str,
    context: CertifiedScenarioBaseline,
    ledger: TemporalLedger,
    rule: HistoricalEvidenceRule,
    registry: Mapping[str, object],
) -> HistoricalEvidenceSet:
    if not evidence_set_id.strip():
        raise ValueError("evidence_set_id required")
    if registry["policy"]["require_certified_b_context"] and not context.context_fingerprint:
        raise ValueError("certified M13-006B context required")
    if registry["policy"]["require_temporal_lineage"] and not validate_ledger_replay(ledger):
        raise ValueError("temporal ledger replay failed")

    rows = [_to_item(x) for x in ledger.entries if _matches(x, rule)]
    rows = sorted(rows, key=lambda x: (x.valid_from, x.known_at, x.entry_id))
    if len(rows) > rule.maximum_items:
        rows = rows[-rule.maximum_items:]

    requested = rule.fact_keys
    matched = tuple(sorted(set(x.fact_key for x in rows)))
    missing = tuple(sorted(set(requested) - set(matched)))
    if not rows:
        coverage = "NONE"
    elif len(rows) < rule.minimum_items or missing:
        coverage = "PARTIAL"
    else:
        coverage = "SUFFICIENT"
    if coverage not in set(registry["coverage_states"]):
        raise ValueError("invalid coverage state")

    limitations = set(context.limitations)
    limitations.update(item for row in rows for item in row.limitations if item)
    if missing:
        limitations.add("Historical evidence coverage is incomplete for requested fact keys.")
    if not rows:
        limitations.add("No governed historical evidence matched the frozen retrieval rule.")

    payload = {
        "evidence_set_id": evidence_set_id,
        "scenario_id": context.scenario_id,
        "certified_context_fingerprint": context.context_fingerprint,
        "temporal_ledger_fingerprint": ledger.ledger_fingerprint,
        "rule_fingerprint": rule.rule_fingerprint,
        "items": tuple(asdict(x) for x in rows),
        "coverage_state": coverage,
        "requested_fact_keys": requested,
        "matched_fact_keys": matched,
        "missing_fact_keys": missing,
        "limitations": tuple(sorted(limitations)),
    }
    return HistoricalEvidenceSet(
        evidence_set_id=evidence_set_id,
        scenario_id=context.scenario_id,
        certified_context_fingerprint=context.context_fingerprint,
        temporal_ledger_fingerprint=ledger.ledger_fingerprint,
        rule_fingerprint=rule.rule_fingerprint,
        items=tuple(rows),
        coverage_state=coverage,
        requested_fact_keys=requested,
        matched_fact_keys=matched,
        missing_fact_keys=missing,
        limitations=payload["limitations"],
        evidence_set_fingerprint=_hash(payload),
    )


def validate_historical_evidence_replay(
    evidence_set: HistoricalEvidenceSet,
    *,
    context: CertifiedScenarioBaseline,
    ledger: TemporalLedger,
    rule: HistoricalEvidenceRule,
    registry: Mapping[str, object],
) -> bool:
    replay = retrieve_historical_evidence(
        evidence_set_id=evidence_set.evidence_set_id,
        context=context,
        ledger=ledger,
        rule=rule,
        registry=registry,
    )
    return replay == evidence_set
