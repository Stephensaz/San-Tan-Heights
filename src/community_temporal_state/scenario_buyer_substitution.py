from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
from typing import Mapping

import yaml

from src.community_temporal_state.scenario_baseline import CertifiedScenarioBaseline
from src.community_temporal_state.scenario_evidence import ScenarioEvidenceSet
from src.community_temporal_state.scenario_pricing_timing import PricingTimingScenarioState


def _canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _hash(value: object) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _validate_fp(value: str, label: str) -> None:
    if len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
        raise ValueError(f"{label} must be lowercase sha256")


def load_buyer_substitution_registry(path: str | Path) -> dict:
    data = yaml.safe_load(Path(path).read_text())
    if data.get("status") != "FROZEN" or data.get("ticket") != "M13-006E":
        raise ValueError("M13-006E buyer/substitution registry must be FROZEN")
    if data.get("buyer_substitution_registry_id") != "STH-M13-006E-BUYER-SUBSTITUTION-v1.0":
        raise ValueError("unexpected M13-006E buyer/substitution registry id")
    return data


@dataclass(frozen=True)
class NumericDimensionPosition:
    dimension: str
    candidate_value: float
    reference_fact_key: str
    reference_value: float
    absolute_difference: float
    direction: str
    position_fingerprint: str


@dataclass(frozen=True)
class CategoricalDimensionPosition:
    dimension: str
    candidate_value: str
    reference_fact_key: str
    reference_value: str
    relation: str
    position_fingerprint: str


@dataclass(frozen=True)
class BuyerSubstitutionCompetitiveState:
    scenario_id: str
    scenario_context_fingerprint: str
    scenario_evidence_fingerprint: str
    pricing_timing_state_fingerprint: str
    buyer_depth: NumericDimensionPosition | None
    comparable_depth: NumericDimensionPosition | None
    resale_competition: NumericDimensionPosition | None
    substitution_requirement: CategoricalDimensionPosition | None
    scarcity_context: tuple[str, object] | None
    included_historical_evidence_count: int
    applicable_pattern_ids: tuple[str, ...]
    unknown_pattern_ids: tuple[str, ...]
    unknowns: tuple[str, ...]
    limitations: tuple[str, ...]
    state_fingerprint: str


def _first_fact(facts: Mapping[str, object], keys: list[str]) -> tuple[str, object] | None:
    for key in keys:
        if key in facts:
            return key, facts[key]
    return None


def _numeric_position(dimension: str, candidate: object, fact_key: str, reference: object) -> NumericDimensionPosition:
    if isinstance(candidate, bool) or not isinstance(candidate, (int, float)) or float(candidate) < 0:
        raise ValueError(f"{dimension} candidate must be non-negative numeric")
    if isinstance(reference, bool) or not isinstance(reference, (int, float)) or float(reference) < 0:
        raise ValueError(f"{dimension} reference must be non-negative numeric")
    candidate_f=float(candidate)
    reference_f=float(reference)
    difference=round(candidate_f-reference_f,6)
    direction="SAME" if difference==0 else ("ABOVE_REFERENCE" if difference>0 else "BELOW_REFERENCE")
    payload={
        "dimension":dimension,
        "candidate_value":candidate_f,
        "reference_fact_key":fact_key,
        "reference_value":reference_f,
        "absolute_difference":difference,
        "direction":direction,
    }
    return NumericDimensionPosition(**payload,position_fingerprint=_hash(payload))


def _categorical_position(dimension: str, candidate: object, fact_key: str, reference: object) -> CategoricalDimensionPosition:
    if not isinstance(candidate,str) or not candidate.strip():
        raise ValueError(f"{dimension} candidate must be non-empty text")
    if not isinstance(reference,str) or not reference.strip():
        raise ValueError(f"{dimension} reference must be non-empty text")
    c=candidate.strip()
    r=reference.strip()
    relation="SAME" if c==r else "DIFFERENT"
    payload={
        "dimension":dimension,
        "candidate_value":c,
        "reference_fact_key":fact_key,
        "reference_value":r,
        "relation":relation,
    }
    return CategoricalDimensionPosition(**payload,position_fingerprint=_hash(payload))


def build_buyer_substitution_competitive_state(
    *,
    context: CertifiedScenarioBaseline,
    evidence_set: ScenarioEvidenceSet,
    pricing_timing_state: PricingTimingScenarioState,
    registry: Mapping[str, object],
) -> BuyerSubstitutionCompetitiveState:
    for label,fp in (
        ("scenario context fingerprint",context.context_fingerprint),
        ("scenario evidence fingerprint",evidence_set.evidence_set_fingerprint),
        ("pricing timing state fingerprint",pricing_timing_state.state_fingerprint),
    ):
        _validate_fp(fp,label)
    if evidence_set.scenario_id!=context.scenario_id or pricing_timing_state.scenario_id!=context.scenario_id:
        raise ValueError("scenario identity mismatch")
    if evidence_set.scenario_context_fingerprint!=context.context_fingerprint:
        raise ValueError("scenario context/evidence lineage mismatch")
    if pricing_timing_state.scenario_context_fingerprint!=context.context_fingerprint:
        raise ValueError("scenario context/pricing timing lineage mismatch")
    if pricing_timing_state.scenario_evidence_fingerprint!=evidence_set.evidence_set_fingerprint:
        raise ValueError("evidence/pricing timing lineage mismatch")

    facts=dict(context.facts)
    assumptions=dict(context.assumptions)
    dimensions=registry["dimensions"]
    unknowns=set(context.unknowns)|set(evidence_set.unknowns)|set(pricing_timing_state.unknowns)
    limitations=set(context.limitations)|set(evidence_set.limitations)|set(pricing_timing_state.limitations)

    numeric={}
    for name in ("buyer_depth","comparable_depth","resale_competition"):
        spec=dimensions[name]
        assumption_key=spec["assumption_key"]
        if assumption_key not in assumptions:
            numeric[name]=None
            unknowns.add(f"EXPLICIT_{name.upper()}_ASSUMPTION_NOT_PROVIDED")
            continue
        ref=_first_fact(facts,list(spec["reference_fact_keys"]))
        if ref is None:
            numeric[name]=None
            unknowns.add(f"CERTIFIED_{name.upper()}_REFERENCE_NOT_AVAILABLE")
            continue
        numeric[name]=_numeric_position(name,assumptions[assumption_key],ref[0],ref[1])

    sub_spec=dimensions["substitution_requirement"]
    substitution=None
    if sub_spec["assumption_key"] not in assumptions:
        unknowns.add("EXPLICIT_SUBSTITUTION_REQUIREMENT_ASSUMPTION_NOT_PROVIDED")
    else:
        ref=_first_fact(facts,list(sub_spec["reference_fact_keys"]))
        if ref is None:
            unknowns.add("CERTIFIED_SUBSTITUTION_REQUIREMENT_REFERENCE_NOT_AVAILABLE")
        else:
            substitution=_categorical_position(
                "substitution_requirement",
                assumptions[sub_spec["assumption_key"]],
                ref[0],
                ref[1],
            )

    scarcity_spec=dimensions["scarcity_context"]
    scarcity=_first_fact(facts,list(scarcity_spec["reference_fact_keys"]))
    if scarcity is None:
        unknowns.add("CERTIFIED_SCARCITY_CONTEXT_NOT_AVAILABLE")

    applicable=tuple(sorted(p.pattern_id for p in context.pattern_applicability if p.state=="APPLICABLE"))
    unknown_patterns=tuple(sorted(p.pattern_id for p in context.pattern_applicability if p.state=="UNKNOWN"))
    limitations.add("Buyer depth, substitution, competition, and scarcity states are descriptive scenario context, not buyer-behavior predictions or recommendations.")

    payload={
        "scenario_id":context.scenario_id,
        "scenario_context_fingerprint":context.context_fingerprint,
        "scenario_evidence_fingerprint":evidence_set.evidence_set_fingerprint,
        "pricing_timing_state_fingerprint":pricing_timing_state.state_fingerprint,
        "buyer_depth":asdict(numeric["buyer_depth"]) if numeric["buyer_depth"] else None,
        "comparable_depth":asdict(numeric["comparable_depth"]) if numeric["comparable_depth"] else None,
        "resale_competition":asdict(numeric["resale_competition"]) if numeric["resale_competition"] else None,
        "substitution_requirement":asdict(substitution) if substitution else None,
        "scarcity_context":scarcity,
        "included_historical_evidence_count":len(evidence_set.included),
        "applicable_pattern_ids":applicable,
        "unknown_pattern_ids":unknown_patterns,
        "unknowns":tuple(sorted(unknowns)),
        "limitations":tuple(sorted(limitations)),
    }
    return BuyerSubstitutionCompetitiveState(
        scenario_id=payload["scenario_id"],
        scenario_context_fingerprint=payload["scenario_context_fingerprint"],
        scenario_evidence_fingerprint=payload["scenario_evidence_fingerprint"],
        pricing_timing_state_fingerprint=payload["pricing_timing_state_fingerprint"],
        buyer_depth=numeric["buyer_depth"],
        comparable_depth=numeric["comparable_depth"],
        resale_competition=numeric["resale_competition"],
        substitution_requirement=substitution,
        scarcity_context=scarcity,
        included_historical_evidence_count=payload["included_historical_evidence_count"],
        applicable_pattern_ids=applicable,
        unknown_pattern_ids=unknown_patterns,
        unknowns=payload["unknowns"],
        limitations=payload["limitations"],
        state_fingerprint=_hash(payload),
    )


def validate_buyer_substitution_state_replay(
    state: BuyerSubstitutionCompetitiveState,
    *,
    context: CertifiedScenarioBaseline,
    evidence_set: ScenarioEvidenceSet,
    pricing_timing_state: PricingTimingScenarioState,
    registry: Mapping[str, object],
) -> bool:
    return build_buyer_substitution_competitive_state(
        context=context,
        evidence_set=evidence_set,
        pricing_timing_state=pricing_timing_state,
        registry=registry,
    )==state
