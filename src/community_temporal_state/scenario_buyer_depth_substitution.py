from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
from statistics import mean
from typing import Mapping, Sequence

import yaml

from src.community_temporal_state.scenario_baseline import CertifiedScenarioBaseline
from src.community_temporal_state.scenario_evidence import ScenarioEvidenceSet, ScenarioEvidenceRecord
from src.community_temporal_state.scenario_pricing_timing import PricingTimingScenarioState


def _canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _hash(value: object) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _validate_fp(value: str, label: str) -> None:
    if len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
        raise ValueError(f"{label} must be lowercase sha256")


def load_buyer_depth_substitution_registry(path: str | Path) -> dict:
    data = yaml.safe_load(Path(path).read_text())
    if data.get("status") != "FROZEN" or data.get("ticket") != "M13-006E":
        raise ValueError("M13-006E buyer-depth/substitution registry must be FROZEN")
    if data.get("buyer_depth_substitution_registry_id") != "STH-M13-006E-BUYER-DEPTH-SUBSTITUTION-v1.0":
        raise ValueError("unexpected M13-006E buyer-depth/substitution registry id")
    return data


@dataclass(frozen=True)
class DescriptiveScenarioPosition:
    dimension: str
    candidate_value: object
    reference_fact_key: str
    reference_value: object
    relation: str
    absolute_difference: float | None
    percent_difference: float | None
    position_fingerprint: str


@dataclass(frozen=True)
class HistoricalNumericSummary:
    dimension: str
    fact_keys: tuple[str, ...]
    observation_count: int
    minimum: float | None
    maximum: float | None
    mean: float | None
    latest: float | None
    entry_fingerprints: tuple[str, ...]
    summary_fingerprint: str


@dataclass(frozen=True)
class BuyerDepthSubstitutionCompetitiveState:
    scenario_id: str
    scenario_context_fingerprint: str
    scenario_evidence_fingerprint: str
    pricing_timing_state_fingerprint: str
    buyer_depth_position: DescriptiveScenarioPosition | None
    substitution_position: DescriptiveScenarioPosition | None
    competitive_set_position: DescriptiveScenarioPosition | None
    buyer_depth_history: HistoricalNumericSummary
    substitution_history: HistoricalNumericSummary
    competitive_set_history: HistoricalNumericSummary
    included_historical_evidence_count: int
    excluded_historical_evidence_count: int
    evidence_source_fingerprints: tuple[str, ...]
    applicable_pattern_ids: tuple[str, ...]
    unknown_pattern_ids: tuple[str, ...]
    unknowns: tuple[str, ...]
    limitations: tuple[str, ...]
    state_fingerprint: str


def _validate_d_state(state: PricingTimingScenarioState) -> bool:
    payload = asdict(state)
    fingerprint = payload.pop("state_fingerprint")
    return _hash(payload) == fingerprint


def _first_fact(facts: Mapping[str, object], keys: Sequence[str]) -> tuple[str, object] | None:
    for key in keys:
        if key in facts:
            return key, facts[key]
    return None


def _numeric(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _position(
    *,
    dimension: str,
    candidate: object,
    reference_fact_key: str,
    reference: object,
) -> DescriptiveScenarioPosition:
    candidate_num = _numeric(candidate)
    reference_num = _numeric(reference)
    if (candidate_num is None) != (reference_num is None):
        raise ValueError(f"{dimension} candidate/reference types must both be numeric or both be categorical")
    if candidate_num is not None and reference_num is not None:
        absolute = round(candidate_num - reference_num, 6)
        percent = None if reference_num == 0 else round((absolute / reference_num) * 100.0, 6)
        relation = "SAME" if absolute == 0 else ("ABOVE_REFERENCE" if absolute > 0 else "BELOW_REFERENCE")
        candidate_value: object = candidate_num
        reference_value: object = reference_num
    else:
        if not isinstance(candidate, str) or not candidate.strip():
            raise ValueError(f"{dimension} candidate value must be non-empty text or numeric")
        if not isinstance(reference, str) or not reference.strip():
            raise ValueError(f"{dimension} reference value must be non-empty text or numeric")
        candidate_value = candidate.strip()
        reference_value = reference.strip()
        absolute = None
        percent = None
        relation = "SAME" if candidate_value == reference_value else "DIFFERENT"
    payload = {
        "dimension": dimension,
        "candidate_value": candidate_value,
        "reference_fact_key": reference_fact_key,
        "reference_value": reference_value,
        "relation": relation,
        "absolute_difference": absolute,
        "percent_difference": percent,
    }
    return DescriptiveScenarioPosition(**payload, position_fingerprint=_hash(payload))


def _historical_summary(
    *,
    dimension: str,
    evidence: Sequence[ScenarioEvidenceRecord],
    fact_keys: Sequence[str],
) -> HistoricalNumericSummary:
    key_set = set(fact_keys)
    rows = [row for row in evidence if row.fact_key in key_set]
    numeric_rows = [(row, _numeric(row.fact_value)) for row in rows]
    numeric_rows = [(row, value) for row, value in numeric_rows if value is not None]
    values = [value for _, value in numeric_rows]
    latest = numeric_rows[-1][1] if numeric_rows else None
    payload = {
        "dimension": dimension,
        "fact_keys": tuple(fact_keys),
        "observation_count": len(values),
        "minimum": round(min(values), 6) if values else None,
        "maximum": round(max(values), 6) if values else None,
        "mean": round(mean(values), 6) if values else None,
        "latest": round(latest, 6) if latest is not None else None,
        "entry_fingerprints": tuple(row.entry_fingerprint for row, _ in numeric_rows),
    }
    return HistoricalNumericSummary(**payload, summary_fingerprint=_hash(payload))


def _build_optional_position(
    *,
    dimension: str,
    assumptions: Mapping[str, object],
    facts: Mapping[str, object],
    assumption_key: str,
    reference_keys: Sequence[str],
    unknowns: set[str],
) -> DescriptiveScenarioPosition | None:
    if assumption_key not in assumptions:
        unknowns.add(f"EXPLICIT_{dimension.upper()}_ASSUMPTION_NOT_PROVIDED")
        return None
    ref = _first_fact(facts, reference_keys)
    if ref is None:
        unknowns.add(f"CERTIFIED_{dimension.upper()}_REFERENCE_NOT_AVAILABLE")
        return None
    return _position(
        dimension=dimension,
        candidate=assumptions[assumption_key],
        reference_fact_key=ref[0],
        reference=ref[1],
    )


def build_buyer_depth_substitution_state(
    *,
    context: CertifiedScenarioBaseline,
    evidence_set: ScenarioEvidenceSet,
    pricing_timing_state: PricingTimingScenarioState,
    registry: Mapping[str, object],
) -> BuyerDepthSubstitutionCompetitiveState:
    _validate_fp(context.context_fingerprint, "scenario context fingerprint")
    _validate_fp(evidence_set.evidence_set_fingerprint, "scenario evidence fingerprint")
    _validate_fp(pricing_timing_state.state_fingerprint, "pricing/timing state fingerprint")
    if not _validate_d_state(pricing_timing_state):
        raise ValueError("pricing/timing state replay failed")
    if evidence_set.scenario_id != context.scenario_id or pricing_timing_state.scenario_id != context.scenario_id:
        raise ValueError("scenario identity mismatch")
    if evidence_set.scenario_context_fingerprint != context.context_fingerprint:
        raise ValueError("scenario context/evidence lineage mismatch")
    if pricing_timing_state.scenario_context_fingerprint != context.context_fingerprint:
        raise ValueError("scenario context/pricing-timing lineage mismatch")
    if pricing_timing_state.scenario_evidence_fingerprint != evidence_set.evidence_set_fingerprint:
        raise ValueError("evidence/pricing-timing lineage mismatch")

    policy = registry["policy"]
    facts = dict(context.facts)
    assumptions = dict(context.assumptions)
    unknowns = set(context.unknowns) | set(evidence_set.unknowns) | set(pricing_timing_state.unknowns)
    limitations = set(context.limitations) | set(evidence_set.limitations) | set(pricing_timing_state.limitations)

    buyer = _build_optional_position(
        dimension="buyer_depth",
        assumptions=assumptions,
        facts=facts,
        assumption_key=policy["candidate_buyer_depth_assumption_key"],
        reference_keys=policy["reference_buyer_depth_fact_keys"],
        unknowns=unknowns,
    )
    substitution = _build_optional_position(
        dimension="substitution_requirement",
        assumptions=assumptions,
        facts=facts,
        assumption_key=policy["candidate_substitution_requirement_assumption_key"],
        reference_keys=policy["reference_substitution_fact_keys"],
        unknowns=unknowns,
    )
    competitive = _build_optional_position(
        dimension="competitive_set_size",
        assumptions=assumptions,
        facts=facts,
        assumption_key=policy["candidate_competitive_set_size_assumption_key"],
        reference_keys=policy["reference_competitive_set_fact_keys"],
        unknowns=unknowns,
    )

    buyer_history = _historical_summary(
        dimension="buyer_depth",
        evidence=evidence_set.included,
        fact_keys=policy["historical_buyer_depth_fact_keys"],
    )
    substitution_history = _historical_summary(
        dimension="substitution_requirement",
        evidence=evidence_set.included,
        fact_keys=policy["historical_substitution_fact_keys"],
    )
    competitive_history = _historical_summary(
        dimension="competitive_set_size",
        evidence=evidence_set.included,
        fact_keys=policy["historical_competitive_set_fact_keys"],
    )
    if buyer_history.observation_count == 0:
        unknowns.add("NO_NUMERIC_BUYER_DEPTH_HISTORY_IN_GOVERNED_EVIDENCE")
    if substitution_history.observation_count == 0:
        unknowns.add("NO_NUMERIC_SUBSTITUTION_HISTORY_IN_GOVERNED_EVIDENCE")
    if competitive_history.observation_count == 0:
        unknowns.add("NO_NUMERIC_COMPETITIVE_SET_HISTORY_IN_GOVERNED_EVIDENCE")

    applicable = tuple(sorted(
        p.pattern_id for p in context.pattern_applicability if p.state == "APPLICABLE"
    ))
    unknown_patterns = tuple(sorted(
        p.pattern_id for p in context.pattern_applicability if p.state == "UNKNOWN"
    ))
    limitations.add(
        "Buyer-depth, substitution, competitive-set positions, and historical distributions are descriptive scenario calculations only; they do not forecast demand or recommend an action."
    )

    payload = {
        "scenario_id": context.scenario_id,
        "scenario_context_fingerprint": context.context_fingerprint,
        "scenario_evidence_fingerprint": evidence_set.evidence_set_fingerprint,
        "pricing_timing_state_fingerprint": pricing_timing_state.state_fingerprint,
        "buyer_depth_position": asdict(buyer) if buyer else None,
        "substitution_position": asdict(substitution) if substitution else None,
        "competitive_set_position": asdict(competitive) if competitive else None,
        "buyer_depth_history": asdict(buyer_history),
        "substitution_history": asdict(substitution_history),
        "competitive_set_history": asdict(competitive_history),
        "included_historical_evidence_count": len(evidence_set.included),
        "excluded_historical_evidence_count": len(evidence_set.excluded),
        "evidence_source_fingerprints": tuple(evidence_set.source_fingerprints),
        "applicable_pattern_ids": applicable,
        "unknown_pattern_ids": unknown_patterns,
        "unknowns": tuple(sorted(unknowns)),
        "limitations": tuple(sorted(limitations)),
    }
    return BuyerDepthSubstitutionCompetitiveState(
        scenario_id=payload["scenario_id"],
        scenario_context_fingerprint=payload["scenario_context_fingerprint"],
        scenario_evidence_fingerprint=payload["scenario_evidence_fingerprint"],
        pricing_timing_state_fingerprint=payload["pricing_timing_state_fingerprint"],
        buyer_depth_position=buyer,
        substitution_position=substitution,
        competitive_set_position=competitive,
        buyer_depth_history=buyer_history,
        substitution_history=substitution_history,
        competitive_set_history=competitive_history,
        included_historical_evidence_count=payload["included_historical_evidence_count"],
        excluded_historical_evidence_count=payload["excluded_historical_evidence_count"],
        evidence_source_fingerprints=payload["evidence_source_fingerprints"],
        applicable_pattern_ids=applicable,
        unknown_pattern_ids=unknown_patterns,
        unknowns=payload["unknowns"],
        limitations=payload["limitations"],
        state_fingerprint=_hash(payload),
    )


def validate_buyer_depth_substitution_replay(
    state: BuyerDepthSubstitutionCompetitiveState,
    *,
    context: CertifiedScenarioBaseline,
    evidence_set: ScenarioEvidenceSet,
    pricing_timing_state: PricingTimingScenarioState,
    registry: Mapping[str, object],
) -> bool:
    return build_buyer_depth_substitution_state(
        context=context,
        evidence_set=evidence_set,
        pricing_timing_state=pricing_timing_state,
        registry=registry,
    ) == state
