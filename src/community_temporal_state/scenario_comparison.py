from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib, json
from pathlib import Path
from typing import Mapping, Sequence
import yaml

from src.community_temporal_state.scenario_baseline import CertifiedScenarioBaseline
from src.community_temporal_state.scenario_evidence import ScenarioEvidenceSet
from src.community_temporal_state.scenario_pricing_timing import PricingTimingScenarioState
from src.community_temporal_state.scenario_buyer_substitution import BuyerSubstitutionCompetitiveState
from src.community_temporal_state.scenario_new_construction import NewConstructionScenarioState


def _canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _hash(value: object) -> str:
    return hashlib.sha256(_canonical_json(value).encode()).hexdigest()


def _validate_fp(value: str, label: str) -> None:
    if len(value)!=64 or any(c not in "0123456789abcdef" for c in value):
        raise ValueError(f"{label} must be lowercase sha256")


def load_scenario_comparison_registry(path: str | Path) -> dict:
    data=yaml.safe_load(Path(path).read_text())
    if data.get("status")!="FROZEN" or data.get("ticket")!="M13-006G":
        raise ValueError("M13-006G comparison registry must be FROZEN")
    if data.get("scenario_comparison_registry_id")!="STH-M13-006G-SCENARIO-COMPARISON-v1.0":
        raise ValueError("unexpected M13-006G registry id")
    return data


@dataclass(frozen=True)
class ScenarioComparisonMember:
    scenario_id: str
    user_order: int
    scenario_context_fingerprint: str
    scenario_evidence_fingerprint: str
    pricing_timing_state_fingerprint: str
    buyer_substitution_state_fingerprint: str
    new_construction_state_fingerprint: str
    dimensions: tuple[tuple[str, object], ...]
    known_dimension_count: int
    total_dimension_count: int
    unknowns: tuple[str, ...]
    limitations: tuple[str, ...]
    member_fingerprint: str


@dataclass(frozen=True)
class ScenarioDimensionDifference:
    left_scenario_id: str
    right_scenario_id: str
    dimension: str
    left_value: object
    right_value: object
    relation: str
    difference_fingerprint: str


@dataclass(frozen=True)
class MultiScenarioComparison:
    comparison_id: str
    scenario_ids: tuple[str, ...]
    member_fingerprints: tuple[str, ...]
    pairwise_differences: tuple[ScenarioDimensionDifference, ...]
    unknowns: tuple[str, ...]
    limitations: tuple[str, ...]
    comparison_fingerprint: str


def _dimension_values(
    *,
    context: CertifiedScenarioBaseline,
    evidence_set: ScenarioEvidenceSet,
    d: PricingTimingScenarioState,
    e: BuyerSubstitutionCompetitiveState,
    f: NewConstructionScenarioState,
) -> dict[str, object]:
    return {
        "pricing_position_percent": d.pricing_position.percent_difference if d.pricing_position else None,
        "listing_timing_days": d.listing_timing.day_difference if d.listing_timing else None,
        "buyer_depth": e.buyer_depth.candidate_value if e.buyer_depth else None,
        "comparable_depth": e.comparable_depth.candidate_value if e.comparable_depth else None,
        "substitution_requirement": e.substitution_requirement.candidate_value if e.substitution_requirement else None,
        "scarcity_context": e.scarcity_context[1] if e.scarcity_context else None,
        "resale_competition": e.resale_competition.candidate_value if e.resale_competition else None,
        "new_construction_competition": f.new_construction_competition.candidate_value if f.new_construction_competition else None,
        "builder_inventory": f.builder_inventory.candidate_value if f.builder_inventory else None,
        "builder_incentive_value": f.builder_incentive_value.candidate_value if f.builder_incentive_value else None,
        "builder_incentive_posture": f.builder_incentive_posture.candidate_value if f.builder_incentive_posture else None,
        "applicable_patterns": tuple(e.applicable_pattern_ids),
        "historical_evidence_count": e.included_historical_evidence_count,
    }


def build_comparison_member(
    *,
    user_order: int,
    context: CertifiedScenarioBaseline,
    evidence_set: ScenarioEvidenceSet,
    pricing_timing_state: PricingTimingScenarioState,
    buyer_substitution_state: BuyerSubstitutionCompetitiveState,
    new_construction_state: NewConstructionScenarioState,
    registry: Mapping[str, object],
) -> ScenarioComparisonMember:
    if user_order<0:
        raise ValueError("user_order cannot be negative")
    for label,fp in (
        ("context",context.context_fingerprint),
        ("evidence",evidence_set.evidence_set_fingerprint),
        ("pricing timing",pricing_timing_state.state_fingerprint),
        ("buyer substitution",buyer_substitution_state.state_fingerprint),
        ("new construction",new_construction_state.state_fingerprint),
    ):
        _validate_fp(fp,f"{label} fingerprint")
    sid=context.scenario_id
    if any(x!=sid for x in (evidence_set.scenario_id,pricing_timing_state.scenario_id,buyer_substitution_state.scenario_id,new_construction_state.scenario_id)):
        raise ValueError("scenario identity mismatch")
    if evidence_set.scenario_context_fingerprint!=context.context_fingerprint:
        raise ValueError("context/evidence lineage mismatch")
    if pricing_timing_state.scenario_context_fingerprint!=context.context_fingerprint:
        raise ValueError("context/D lineage mismatch")
    if buyer_substitution_state.scenario_context_fingerprint!=context.context_fingerprint:
        raise ValueError("context/E lineage mismatch")
    if new_construction_state.scenario_context_fingerprint!=context.context_fingerprint:
        raise ValueError("context/F lineage mismatch")
    if buyer_substitution_state.pricing_timing_state_fingerprint!=pricing_timing_state.state_fingerprint:
        raise ValueError("D/E lineage mismatch")
    if new_construction_state.buyer_substitution_state_fingerprint!=buyer_substitution_state.state_fingerprint:
        raise ValueError("E/F lineage mismatch")

    values=_dimension_values(context=context,evidence_set=evidence_set,d=pricing_timing_state,e=buyer_substitution_state,f=new_construction_state)
    allowed=list(registry["governed_dimensions"])
    base_dimensions=[x for x in allowed if x not in {"known_dimension_count","total_dimension_count","unknowns"}]
    known=sum(values.get(k) is not None for k in base_dimensions)
    total=len(base_dimensions)
    values["known_dimension_count"]=known
    values["total_dimension_count"]=total
    values["unknowns"]=tuple(sorted(set(context.unknowns)|set(evidence_set.unknowns)|set(pricing_timing_state.unknowns)|set(buyer_substitution_state.unknowns)|set(new_construction_state.unknowns)))
    dimensions=tuple((k,values.get(k)) for k in allowed)
    limitations=tuple(sorted(set(context.limitations)|set(evidence_set.limitations)|set(pricing_timing_state.limitations)|set(buyer_substitution_state.limitations)|set(new_construction_state.limitations)|{"Scenario comparison is descriptive only; no scenario is ranked, scored, selected, or recommended."}))
    payload={
        "scenario_id":sid,"user_order":user_order,
        "scenario_context_fingerprint":context.context_fingerprint,
        "scenario_evidence_fingerprint":evidence_set.evidence_set_fingerprint,
        "pricing_timing_state_fingerprint":pricing_timing_state.state_fingerprint,
        "buyer_substitution_state_fingerprint":buyer_substitution_state.state_fingerprint,
        "new_construction_state_fingerprint":new_construction_state.state_fingerprint,
        "dimensions":dimensions,"known_dimension_count":known,"total_dimension_count":total,
        "unknowns":values["unknowns"],"limitations":limitations,
    }
    return ScenarioComparisonMember(**payload,member_fingerprint=_hash(payload))


def _relation(left: object,right: object) -> str:
    if left is None and right is None: return "SAME"
    if left is None: return "LEFT_MISSING"
    if right is None: return "RIGHT_MISSING"
    if left==right: return "SAME"
    if isinstance(left,(int,float)) and not isinstance(left,bool) and isinstance(right,(int,float)) and not isinstance(right,bool):
        return "LEFT_LOWER" if left<right else "LEFT_HIGHER"
    return "DIFFERENT"


def compare_scenario_members(*, comparison_id: str, members: Sequence[ScenarioComparisonMember], registry: Mapping[str, object]) -> MultiScenarioComparison:
    if not comparison_id.strip():
        raise ValueError("comparison_id required")
    if len(members)<2:
        raise ValueError("at least two scenarios required")
    ordered=tuple(sorted(members,key=lambda x:x.user_order))
    if len({x.user_order for x in ordered})!=len(ordered):
        raise ValueError("unique user_order required")
    if len({x.scenario_id for x in ordered})!=len(ordered):
        raise ValueError("unique scenario ids required")
    differences=[]
    governed=tuple(registry["governed_dimensions"])
    for i,left in enumerate(ordered):
        lv=dict(left.dimensions)
        for right in ordered[i+1:]:
            rv=dict(right.dimensions)
            for dimension in governed:
                payload={
                    "left_scenario_id":left.scenario_id,
                    "right_scenario_id":right.scenario_id,
                    "dimension":dimension,
                    "left_value":lv.get(dimension),
                    "right_value":rv.get(dimension),
                    "relation":_relation(lv.get(dimension),rv.get(dimension)),
                }
                differences.append(ScenarioDimensionDifference(**payload,difference_fingerprint=_hash(payload)))
    unknowns=tuple(sorted({u for m in ordered for u in m.unknowns}))
    limitations=tuple(sorted({l for m in ordered for l in m.limitations}|{"Pairwise relations describe differences only and do not indicate preference, quality, or expected outcome."}))
    payload={
        "comparison_id":comparison_id,
        "scenario_ids":tuple(m.scenario_id for m in ordered),
        "member_fingerprints":tuple(m.member_fingerprint for m in ordered),
        "pairwise_differences":tuple(asdict(x) for x in differences),
        "unknowns":unknowns,"limitations":limitations,
    }
    return MultiScenarioComparison(
        comparison_id=comparison_id,scenario_ids=payload["scenario_ids"],
        member_fingerprints=payload["member_fingerprints"],pairwise_differences=tuple(differences),
        unknowns=unknowns,limitations=limitations,comparison_fingerprint=_hash(payload)
    )


def validate_comparison_replay(comparison: MultiScenarioComparison, *, members: Sequence[ScenarioComparisonMember], registry: Mapping[str, object]) -> bool:
    return compare_scenario_members(comparison_id=comparison.comparison_id,members=members,registry=registry)==comparison
