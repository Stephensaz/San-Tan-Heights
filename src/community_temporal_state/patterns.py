from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
from typing import Mapping, Sequence

import yaml

from src.community_temporal_state.history import TemporalLedger, validate_ledger_replay


def _canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _hash(value: object) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _validate_fp(value: str, label: str) -> None:
    if len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
        raise ValueError(f"{label} must be lowercase sha256")


def load_evolution_pattern_registry(path: str | Path) -> dict:
    data = yaml.safe_load(Path(path).read_text())
    if data.get("status") != "FROZEN" or data.get("ticket") != "M13-005":
        raise ValueError("M13-005 evolution pattern registry must be FROZEN")
    if data.get("evolution_pattern_registry_id") != "STH-M13-005-EVOLUTION-PATTERNS-v1.0":
        raise ValueError("unexpected M13-005 evolution pattern registry id")
    return data


@dataclass(frozen=True)
class PatternObservation:
    observation_id: str
    property_id: str
    period_id: str
    regime_id: str
    exposure_value: float
    outcome_value: float
    confounder_values: tuple[tuple[str, str], ...]
    source_entry_fingerprints: tuple[str, ...]
    observation_fingerprint: str


@dataclass(frozen=True)
class PatternPopulation:
    population_id: str
    role: str
    domain: str
    inclusion_rule: str
    regime_ids: tuple[str, ...]
    confounder_manifest: tuple[str, ...]
    observation_ids: tuple[str, ...]
    source_entry_fingerprints: tuple[str, ...]
    population_fingerprint: str


@dataclass(frozen=True)
class PatternEstimate:
    population_id: str
    n: int
    distinct_periods: int
    effect_direction: str
    effect_magnitude: float
    estimate_fingerprint: str


@dataclass(frozen=True)
class GovernedPatternCandidate:
    pattern_id: str
    domain: str
    statement: str
    discovery_population_id: str
    validation_population_id: str | None
    replication_population_id: str | None
    discovery_estimate: PatternEstimate
    validation_estimate: PatternEstimate | None
    replication_estimate: PatternEstimate | None
    state: str
    promotion_state: str
    reason_codes: tuple[str, ...]
    limitations: tuple[str, ...]
    source_ledger_fingerprint: str
    candidate_fingerprint: str


def make_pattern_observation(
    *,
    observation_id: str,
    property_id: str,
    period_id: str,
    regime_id: str,
    exposure_value: float,
    outcome_value: float,
    confounder_values: Mapping[str, str],
    source_entry_fingerprints: Sequence[str],
) -> PatternObservation:
    if not all(x.strip() for x in (observation_id, property_id, period_id, regime_id)):
        raise ValueError("observation identity fields required")
    lineage = tuple(sorted(set(source_entry_fingerprints)))
    if not lineage:
        raise ValueError("temporal lineage required")
    for fp in lineage:
        _validate_fp(fp, "source entry fingerprint")
    conf = tuple(sorted((str(k), str(v)) for k, v in confounder_values.items()))
    payload = {
        "observation_id": observation_id,
        "property_id": property_id,
        "period_id": period_id,
        "regime_id": regime_id,
        "exposure_value": float(exposure_value),
        "outcome_value": float(outcome_value),
        "confounder_values": conf,
        "source_entry_fingerprints": lineage,
    }
    return PatternObservation(**payload, observation_fingerprint=_hash(payload))


def build_pattern_population(
    *,
    population_id: str,
    role: str,
    domain: str,
    inclusion_rule: str,
    observations: Sequence[PatternObservation],
    regime_ids: Sequence[str],
    confounder_manifest: Sequence[str],
    registry: Mapping[str, object],
) -> PatternPopulation:
    if role not in {"DISCOVERY", "VALIDATION", "REPLICATION"}:
        raise ValueError("unsupported population role")
    if domain not in set(registry["domains"]):
        raise ValueError("unsupported pattern domain")
    if not inclusion_rule.strip():
        raise ValueError("frozen inclusion rule required")
    if not confounder_manifest and registry["policy"]["require_confounder_manifest"]:
        raise ValueError("confounder manifest required")
    allowed_regimes = set(regime_ids)
    rows = tuple(sorted(
        (x for x in observations if x.regime_id in allowed_regimes),
        key=lambda x: x.observation_id,
    ))
    if len({x.observation_id for x in rows}) != len(rows):
        raise ValueError("duplicate observation ids prohibited")
    source = tuple(sorted({fp for x in rows for fp in x.source_entry_fingerprints}))
    payload = {
        "population_id": population_id,
        "role": role,
        "domain": domain,
        "inclusion_rule": inclusion_rule,
        "regime_ids": tuple(sorted(set(regime_ids))),
        "confounder_manifest": tuple(sorted(set(confounder_manifest))),
        "observation_ids": tuple(x.observation_id for x in rows),
        "source_entry_fingerprints": source,
    }
    return PatternPopulation(**payload, population_fingerprint=_hash(payload))


def estimate_pattern(
    population: PatternPopulation,
    *,
    observations: Sequence[PatternObservation],
    registry: Mapping[str, object],
) -> PatternEstimate:
    by_id = {x.observation_id: x for x in observations}
    rows = [by_id[x] for x in population.observation_ids]
    if not rows:
        raise ValueError("pattern population is empty")
    n = len(rows)
    periods = len({x.period_id for x in rows})
    mean_x = sum(x.exposure_value for x in rows) / n
    mean_y = sum(x.outcome_value for x in rows) / n
    cov = sum((x.exposure_value - mean_x) * (x.outcome_value - mean_y) for x in rows)
    var = sum((x.exposure_value - mean_x) ** 2 for x in rows)
    slope = 0.0 if var == 0 else cov / var
    magnitude = round(abs(slope), 12)
    threshold = float(registry["policy"]["minimum_effect_magnitude"])
    direction = "NULL" if magnitude < threshold else ("POSITIVE" if slope > 0 else "NEGATIVE")
    payload = {
        "population_id": population.population_id,
        "n": n,
        "distinct_periods": periods,
        "effect_direction": direction,
        "effect_magnitude": magnitude,
    }
    return PatternEstimate(**payload, estimate_fingerprint=_hash(payload))


def _independent(a: PatternPopulation, b: PatternPopulation) -> bool:
    return not set(a.observation_ids).intersection(b.observation_ids)


def discover_pattern(
    *,
    pattern_id: str,
    domain: str,
    statement: str,
    discovery_population: PatternPopulation,
    observations: Sequence[PatternObservation],
    ledger: TemporalLedger,
    registry: Mapping[str, object],
    limitations: Sequence[str] = (),
) -> GovernedPatternCandidate:
    if not validate_ledger_replay(ledger):
        raise ValueError("M13-005 requires reproducible M13-004 history")
    if discovery_population.role != "DISCOVERY":
        raise ValueError("discovery population role required")
    if discovery_population.domain != domain:
        raise ValueError("domain mismatch")
    estimate = estimate_pattern(discovery_population, observations=observations, registry=registry)
    reasons = []
    min_n = int(registry["policy"]["minimum_discovery_n"])
    min_periods = int(registry["policy"]["minimum_distinct_periods"])
    if estimate.n < min_n:
        reasons.append("DISCOVERY_SAMPLE_BELOW_MINIMUM")
    if estimate.distinct_periods < min_periods:
        reasons.append("INSUFFICIENT_DISTINCT_PERIODS")
    if estimate.effect_direction == "NULL":
        state = "NULL_RESULT"
        reasons.append("NULL_EFFECT")
    elif reasons:
        state = "NOT_ELIGIBLE"
    else:
        state = "VALIDATION_REQUIRED"
    return _candidate(
        pattern_id=pattern_id,
        domain=domain,
        statement=statement,
        discovery_population=discovery_population,
        discovery_estimate=estimate,
        ledger=ledger,
        state=state,
        promotion_state="INELIGIBLE" if state != "VALIDATION_REQUIRED" else "NOT_EVALUATED",
        reason_codes=tuple(sorted(set(reasons))),
        limitations=tuple(sorted(set(limitations))),
    )


def _candidate(
    *,
    pattern_id: str,
    domain: str,
    statement: str,
    discovery_population: PatternPopulation,
    discovery_estimate: PatternEstimate,
    ledger: TemporalLedger,
    state: str,
    promotion_state: str,
    reason_codes: tuple[str, ...],
    limitations: tuple[str, ...],
    validation_population: PatternPopulation | None = None,
    validation_estimate: PatternEstimate | None = None,
    replication_population: PatternPopulation | None = None,
    replication_estimate: PatternEstimate | None = None,
) -> GovernedPatternCandidate:
    payload = {
        "pattern_id": pattern_id,
        "domain": domain,
        "statement": statement,
        "discovery_population_id": discovery_population.population_id,
        "validation_population_id": validation_population.population_id if validation_population else None,
        "replication_population_id": replication_population.population_id if replication_population else None,
        "discovery_estimate": asdict(discovery_estimate),
        "validation_estimate": asdict(validation_estimate) if validation_estimate else None,
        "replication_estimate": asdict(replication_estimate) if replication_estimate else None,
        "state": state,
        "promotion_state": promotion_state,
        "reason_codes": reason_codes,
        "limitations": limitations,
        "source_ledger_fingerprint": ledger.ledger_fingerprint,
    }
    return GovernedPatternCandidate(
        pattern_id=pattern_id,
        domain=domain,
        statement=statement,
        discovery_population_id=discovery_population.population_id,
        validation_population_id=validation_population.population_id if validation_population else None,
        replication_population_id=replication_population.population_id if replication_population else None,
        discovery_estimate=discovery_estimate,
        validation_estimate=validation_estimate,
        replication_estimate=replication_estimate,
        state=state,
        promotion_state=promotion_state,
        reason_codes=reason_codes,
        limitations=limitations,
        source_ledger_fingerprint=ledger.ledger_fingerprint,
        candidate_fingerprint=_hash(payload),
    )


def validate_and_replicate_pattern(
    *,
    candidate: GovernedPatternCandidate,
    discovery_population: PatternPopulation,
    validation_population: PatternPopulation,
    replication_population: PatternPopulation,
    observations: Sequence[PatternObservation],
    ledger: TemporalLedger,
    registry: Mapping[str, object],
) -> GovernedPatternCandidate:
    if candidate.state != "VALIDATION_REQUIRED":
        raise ValueError("candidate not eligible for validation")
    if validation_population.role != "VALIDATION" or replication_population.role != "REPLICATION":
        raise ValueError("validation and replication roles required")
    if not _independent(discovery_population, validation_population):
        raise ValueError("discovery/validation leakage prohibited")
    if not _independent(discovery_population, replication_population):
        raise ValueError("discovery/replication leakage prohibited")
    if not _independent(validation_population, replication_population):
        raise ValueError("validation/replication leakage prohibited")
    ve = estimate_pattern(validation_population, observations=observations, registry=registry)
    re = estimate_pattern(replication_population, observations=observations, registry=registry)
    reasons: list[str] = []
    policy = registry["policy"]
    if ve.n < int(policy["minimum_validation_n"]):
        reasons.append("VALIDATION_SAMPLE_BELOW_MINIMUM")
    if re.n < int(policy["minimum_replication_n"]):
        reasons.append("REPLICATION_SAMPLE_BELOW_MINIMUM")
    if ve.distinct_periods < int(policy["minimum_distinct_periods"]):
        reasons.append("VALIDATION_PERIODS_BELOW_MINIMUM")
    if re.distinct_periods < int(policy["minimum_distinct_periods"]):
        reasons.append("REPLICATION_PERIODS_BELOW_MINIMUM")
    d = candidate.discovery_estimate.effect_direction
    if policy["require_same_effect_direction"] and (ve.effect_direction != d or re.effect_direction != d):
        reasons.append("EFFECT_DIRECTION_NOT_REPLICATED")
    drift = abs(re.effect_magnitude - ve.effect_magnitude)
    if drift > float(policy["maximum_absolute_replication_drift"]):
        reasons.append("REPLICATION_DRIFT_EXCEEDED")
    if d == "NULL" or ve.effect_direction == "NULL" or re.effect_direction == "NULL":
        reasons.append("NULL_EFFECT_NOT_PROMOTABLE")
    if reasons:
        state = "REPLICATION_FAILED"
        promotion = "INELIGIBLE"
    else:
        state = "REPLICATED"
        promotion = "ELIGIBLE"
    return _candidate(
        pattern_id=candidate.pattern_id,
        domain=candidate.domain,
        statement=candidate.statement,
        discovery_population=discovery_population,
        discovery_estimate=candidate.discovery_estimate,
        validation_population=validation_population,
        validation_estimate=ve,
        replication_population=replication_population,
        replication_estimate=re,
        ledger=ledger,
        state=state,
        promotion_state=promotion,
        reason_codes=tuple(sorted(set((*candidate.reason_codes, *reasons)))),
        limitations=candidate.limitations,
    )


def promote_pattern(
    candidate: GovernedPatternCandidate,
    *,
    ledger: TemporalLedger,
) -> GovernedPatternCandidate:
    if candidate.state != "REPLICATED" or candidate.promotion_state != "ELIGIBLE":
        raise ValueError("pattern is not eligible for promotion")
    if candidate.source_ledger_fingerprint != ledger.ledger_fingerprint or not validate_ledger_replay(ledger):
        raise ValueError("temporal lineage mismatch")
    payload = asdict(candidate)
    payload["state"] = "PROMOTED"
    payload["promotion_state"] = "PROMOTED"
    payload.pop("candidate_fingerprint")
    return GovernedPatternCandidate(
        **payload,
        candidate_fingerprint=_hash(payload),
    )


def validate_candidate_replay(candidate: GovernedPatternCandidate) -> bool:
    payload = asdict(candidate)
    fingerprint = payload.pop("candidate_fingerprint")
    return _hash(payload) == fingerprint
