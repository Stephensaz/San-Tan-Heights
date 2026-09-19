from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date
import hashlib
import json
from pathlib import Path
from typing import Mapping

import yaml

from src.community_temporal_state.scenario_baseline import CertifiedScenarioBaseline
from src.community_temporal_state.scenario_evidence import ScenarioEvidenceSet


def _canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _hash(value: object) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _validate_fp(value: str, label: str) -> None:
    if len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
        raise ValueError(f"{label} must be lowercase sha256")


def load_pricing_timing_registry(path: str | Path) -> dict:
    data = yaml.safe_load(Path(path).read_text())
    if data.get("status") != "FROZEN" or data.get("ticket") != "M13-006D":
        raise ValueError("M13-006D pricing/timing registry must be FROZEN")
    if data.get("pricing_timing_registry_id") != "STH-M13-006D-PRICING-TIMING-v1.0":
        raise ValueError("unexpected M13-006D pricing/timing registry id")
    return data


@dataclass(frozen=True)
class PricingPosition:
    candidate_price: float
    reference_fact_key: str
    reference_price: float
    absolute_difference: float
    percent_difference: float
    direction: str
    position_fingerprint: str


@dataclass(frozen=True)
class ListingTiming:
    candidate_listing_date: str
    reference_fact_key: str
    reference_date: str
    day_difference: int
    direction: str
    timing_fingerprint: str


@dataclass(frozen=True)
class PricingTimingScenarioState:
    scenario_id: str
    scenario_context_fingerprint: str
    scenario_evidence_fingerprint: str
    pricing_position: PricingPosition | None
    listing_timing: ListingTiming | None
    included_historical_evidence_count: int
    excluded_historical_evidence_count: int
    applicable_pattern_ids: tuple[str, ...]
    unknown_pattern_ids: tuple[str, ...]
    evidence_source_fingerprints: tuple[str, ...]
    unknowns: tuple[str, ...]
    limitations: tuple[str, ...]
    state_fingerprint: str


def _first_fact(facts: Mapping[str, object], keys: list[str]) -> tuple[str, object] | None:
    for key in keys:
        if key in facts:
            return key, facts[key]
    return None


def _price_position(candidate: object, fact_key: str, reference: object) -> PricingPosition:
    if isinstance(candidate, bool) or not isinstance(candidate, (int, float)) or candidate < 0:
        raise ValueError("candidate price must be non-negative numeric")
    if isinstance(reference, bool) or not isinstance(reference, (int, float)) or reference <= 0:
        raise ValueError("certified reference price must be positive numeric")
    candidate_f = float(candidate)
    reference_f = float(reference)
    absolute = round(candidate_f - reference_f, 2)
    pct = round((absolute / reference_f) * 100.0, 6)
    direction = "SAME" if absolute == 0 else ("ABOVE_REFERENCE" if absolute > 0 else "BELOW_REFERENCE")
    payload = {
        "candidate_price": candidate_f,
        "reference_fact_key": fact_key,
        "reference_price": reference_f,
        "absolute_difference": absolute,
        "percent_difference": pct,
        "direction": direction,
    }
    return PricingPosition(**payload, position_fingerprint=_hash(payload))


def _listing_timing(candidate: object, fact_key: str, reference: object) -> ListingTiming:
    if not isinstance(candidate, str) or not isinstance(reference, str):
        raise ValueError("candidate and reference listing dates must be ISO date text")
    try:
        candidate_d = date.fromisoformat(candidate)
        reference_d = date.fromisoformat(reference)
    except ValueError as exc:
        raise ValueError("candidate and reference listing dates must be ISO date text") from exc
    days = (candidate_d - reference_d).days
    direction = "SAME_DATE" if days == 0 else ("LATER_THAN_REFERENCE" if days > 0 else "EARLIER_THAN_REFERENCE")
    payload = {
        "candidate_listing_date": candidate,
        "reference_fact_key": fact_key,
        "reference_date": reference,
        "day_difference": days,
        "direction": direction,
    }
    return ListingTiming(**payload, timing_fingerprint=_hash(payload))


def build_pricing_timing_scenario_state(
    *,
    context: CertifiedScenarioBaseline,
    evidence_set: ScenarioEvidenceSet,
    registry: Mapping[str, object],
) -> PricingTimingScenarioState:
    _validate_fp(context.context_fingerprint, "scenario context fingerprint")
    _validate_fp(evidence_set.evidence_set_fingerprint, "scenario evidence fingerprint")
    if evidence_set.scenario_id != context.scenario_id:
        raise ValueError("scenario identity mismatch")
    if evidence_set.scenario_context_fingerprint != context.context_fingerprint:
        raise ValueError("scenario context/evidence lineage mismatch")

    facts = dict(context.facts)
    assumptions = dict(context.assumptions)
    policy = registry["policy"]
    unknowns = set(context.unknowns) | set(evidence_set.unknowns)
    limitations = set(context.limitations) | set(evidence_set.limitations)

    pricing: PricingPosition | None = None
    price_key = policy["candidate_price_assumption_key"]
    if price_key in assumptions:
        ref = _first_fact(facts, list(policy["reference_price_fact_keys"]))
        if ref is None:
            unknowns.add("CERTIFIED_REFERENCE_PRICE_NOT_AVAILABLE")
        else:
            pricing = _price_position(assumptions[price_key], ref[0], ref[1])
    else:
        unknowns.add("EXPLICIT_CANDIDATE_PRICE_NOT_PROVIDED")

    timing: ListingTiming | None = None
    date_key = policy["candidate_date_assumption_key"]
    if date_key in assumptions:
        ref = _first_fact(facts, list(policy["reference_date_fact_keys"]))
        if ref is None:
            unknowns.add("CERTIFIED_REFERENCE_DATE_NOT_AVAILABLE")
        else:
            timing = _listing_timing(assumptions[date_key], ref[0], ref[1])
    else:
        unknowns.add("EXPLICIT_CANDIDATE_LISTING_DATE_NOT_PROVIDED")

    applicable = tuple(sorted(
        p.pattern_id for p in context.pattern_applicability if p.state == "APPLICABLE"
    ))
    unknown_patterns = tuple(sorted(
        p.pattern_id for p in context.pattern_applicability if p.state == "UNKNOWN"
    ))
    limitations.add("Pricing and timing differences are descriptive scenario calculations, not recommendations or forecasts.")

    payload = {
        "scenario_id": context.scenario_id,
        "scenario_context_fingerprint": context.context_fingerprint,
        "scenario_evidence_fingerprint": evidence_set.evidence_set_fingerprint,
        "pricing_position": asdict(pricing) if pricing else None,
        "listing_timing": asdict(timing) if timing else None,
        "included_historical_evidence_count": len(evidence_set.included),
        "excluded_historical_evidence_count": len(evidence_set.excluded),
        "applicable_pattern_ids": applicable,
        "unknown_pattern_ids": unknown_patterns,
        "evidence_source_fingerprints": tuple(evidence_set.source_fingerprints),
        "unknowns": tuple(sorted(unknowns)),
        "limitations": tuple(sorted(limitations)),
    }
    return PricingTimingScenarioState(
        scenario_id=payload["scenario_id"],
        scenario_context_fingerprint=payload["scenario_context_fingerprint"],
        scenario_evidence_fingerprint=payload["scenario_evidence_fingerprint"],
        pricing_position=pricing,
        listing_timing=timing,
        included_historical_evidence_count=payload["included_historical_evidence_count"],
        excluded_historical_evidence_count=payload["excluded_historical_evidence_count"],
        applicable_pattern_ids=applicable,
        unknown_pattern_ids=unknown_patterns,
        evidence_source_fingerprints=payload["evidence_source_fingerprints"],
        unknowns=payload["unknowns"],
        limitations=payload["limitations"],
        state_fingerprint=_hash(payload),
    )


def validate_pricing_timing_state_replay(
    state: PricingTimingScenarioState,
    *,
    context: CertifiedScenarioBaseline,
    evidence_set: ScenarioEvidenceSet,
    registry: Mapping[str, object],
) -> bool:
    return build_pricing_timing_scenario_state(
        context=context,
        evidence_set=evidence_set,
        registry=registry,
    ) == state
