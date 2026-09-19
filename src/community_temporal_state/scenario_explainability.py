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
from src.community_temporal_state.scenario_comparison import ScenarioComparisonMember, MultiScenarioComparison


def _canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _hash(value: object) -> str:
    return hashlib.sha256(_canonical_json(value).encode()).hexdigest()


def _validate_fp(value: str, label: str) -> None:
    if len(value)!=64 or any(c not in "0123456789abcdef" for c in value):
        raise ValueError(f"{label} must be lowercase sha256")


def load_explainability_registry(path: str | Path) -> dict:
    data=yaml.safe_load(Path(path).read_text())
    if data.get("status")!="FROZEN" or data.get("ticket")!="M13-006H":
        raise ValueError("M13-006H explainability registry must be FROZEN")
    if data.get("explainability_registry_id")!="STH-M13-006H-EXPLAINABILITY-v1.0":
        raise ValueError("unexpected M13-006H registry id")
    return data


@dataclass(frozen=True)
class ScenarioExplanation:
    scenario_id: str
    scenario_context_fingerprint: str
    comparison_member_fingerprint: str
    facts: tuple[tuple[str, object], ...]
    assumptions: tuple[tuple[str, object], ...]
    modeled_dimensions: tuple[str, ...]
    changed_from_reference: tuple[str, ...]
    evidence_source_fingerprints: tuple[str, ...]
    evidence_fingerprints: tuple[str, ...]
    applicable_pattern_ids: tuple[str, ...]
    unknown_pattern_ids: tuple[str, ...]
    unknowns: tuple[str, ...]
    limitations: tuple[str, ...]
    explanation_fingerprint: str


@dataclass(frozen=True)
class ComparisonExplanation:
    comparison_id: str
    comparison_fingerprint: str
    scenario_ids: tuple[str, ...]
    scenario_explanation_fingerprints: tuple[str, ...]
    pairwise_differences: tuple[tuple[str, str, str, object, object, str], ...]
    unknowns: tuple[str, ...]
    limitations: tuple[str, ...]
    explanation_fingerprint: str


def _changed_dimensions(d: PricingTimingScenarioState,e: BuyerSubstitutionCompetitiveState,f: NewConstructionScenarioState) -> tuple[str,...]:
    out=[]
    if d.pricing_position and d.pricing_position.direction!="SAME": out.append("pricing_position")
    if d.listing_timing and d.listing_timing.direction!="SAME_DATE": out.append("listing_timing")
    for name,obj in (("buyer_depth",e.buyer_depth),("comparable_depth",e.comparable_depth),("resale_competition",e.resale_competition)):
        if obj and obj.direction!="SAME": out.append(name)
    if e.substitution_requirement and e.substitution_requirement.relation!="SAME": out.append("substitution_requirement")
    for name,obj in (("new_construction_competition",f.new_construction_competition),("builder_inventory",f.builder_inventory),("builder_incentive_value",f.builder_incentive_value)):
        if obj and obj.direction!="SAME": out.append(name)
    if f.builder_incentive_posture and f.builder_incentive_posture.relation!="SAME": out.append("builder_incentive_posture")
    return tuple(out)


def build_scenario_explanation(
    *,
    context: CertifiedScenarioBaseline,
    evidence_set: ScenarioEvidenceSet,
    pricing_timing_state: PricingTimingScenarioState,
    buyer_substitution_state: BuyerSubstitutionCompetitiveState,
    new_construction_state: NewConstructionScenarioState,
    comparison_member: ScenarioComparisonMember,
    registry: Mapping[str, object],
) -> ScenarioExplanation:
    for label,fp in (
        ("context",context.context_fingerprint),("evidence",evidence_set.evidence_set_fingerprint),
        ("D",pricing_timing_state.state_fingerprint),("E",buyer_substitution_state.state_fingerprint),
        ("F",new_construction_state.state_fingerprint),("G member",comparison_member.member_fingerprint),
    ): _validate_fp(fp,f"{label} fingerprint")
    sid=context.scenario_id
    if any(x!=sid for x in (evidence_set.scenario_id,pricing_timing_state.scenario_id,buyer_substitution_state.scenario_id,new_construction_state.scenario_id,comparison_member.scenario_id)):
        raise ValueError("scenario identity mismatch")
    if comparison_member.scenario_context_fingerprint!=context.context_fingerprint:
        raise ValueError("context/G lineage mismatch")
    if comparison_member.scenario_evidence_fingerprint!=evidence_set.evidence_set_fingerprint:
        raise ValueError("evidence/G lineage mismatch")
    if comparison_member.pricing_timing_state_fingerprint!=pricing_timing_state.state_fingerprint:
        raise ValueError("D/G lineage mismatch")
    if comparison_member.buyer_substitution_state_fingerprint!=buyer_substitution_state.state_fingerprint:
        raise ValueError("E/G lineage mismatch")
    if comparison_member.new_construction_state_fingerprint!=new_construction_state.state_fingerprint:
        raise ValueError("F/G lineage mismatch")

    dims=tuple(k for k,v in comparison_member.dimensions if v is not None and k not in {"known_dimension_count","total_dimension_count","unknowns"})
    changed=_changed_dimensions(pricing_timing_state,buyer_substitution_state,new_construction_state)
    unknowns=tuple(sorted(set(context.unknowns)|set(evidence_set.unknowns)|set(pricing_timing_state.unknowns)|set(buyer_substitution_state.unknowns)|set(new_construction_state.unknowns)|set(comparison_member.unknowns)))
    limits=tuple(sorted(set(context.limitations)|set(evidence_set.limitations)|set(pricing_timing_state.limitations)|set(buyer_substitution_state.limitations)|set(new_construction_state.limitations)|set(comparison_member.limitations)|{
        "Historical evidence and promoted patterns describe observed associations only; they are not predictions.",
        "Assumptions remain assumptions and are not certified facts.",
    }))
    payload={
        "scenario_id":sid,"scenario_context_fingerprint":context.context_fingerprint,
        "comparison_member_fingerprint":comparison_member.member_fingerprint,
        "facts":tuple(context.facts),"assumptions":tuple(context.assumptions),
        "modeled_dimensions":dims,"changed_from_reference":changed,
        "evidence_source_fingerprints":tuple(evidence_set.source_fingerprints),
        "evidence_fingerprints":tuple(evidence_set.evidence_fingerprints),
        "applicable_pattern_ids":tuple(dict(comparison_member.dimensions).get("applicable_patterns") or ()),
        "unknown_pattern_ids":tuple(buyer_substitution_state.unknown_pattern_ids),
        "unknowns":unknowns,"limitations":limits,
    }
    return ScenarioExplanation(**payload,explanation_fingerprint=_hash(payload))


def build_comparison_explanation(
    *,
    comparison: MultiScenarioComparison,
    scenario_explanations: Sequence[ScenarioExplanation],
) -> ComparisonExplanation:
    _validate_fp(comparison.comparison_fingerprint,"comparison fingerprint")
    by_id={x.scenario_id:x for x in scenario_explanations}
    if set(by_id)!=set(comparison.scenario_ids):
        raise ValueError("comparison explanation requires exactly one explanation per scenario")
    rows=tuple(
        (x.left_scenario_id,x.right_scenario_id,x.dimension,x.left_value,x.right_value,x.relation)
        for x in comparison.pairwise_differences
    )
    unknowns=tuple(sorted(set(comparison.unknowns)|{u for x in scenario_explanations for u in x.unknowns}))
    limits=tuple(sorted(set(comparison.limitations)|{l for x in scenario_explanations for l in x.limitations}|{
        "Pairwise differences do not establish preference, expected outcome, or causality."
    }))
    payload={
        "comparison_id":comparison.comparison_id,"comparison_fingerprint":comparison.comparison_fingerprint,
        "scenario_ids":comparison.scenario_ids,
        "scenario_explanation_fingerprints":tuple(by_id[s].explanation_fingerprint for s in comparison.scenario_ids),
        "pairwise_differences":rows,"unknowns":unknowns,"limitations":limits,
    }
    return ComparisonExplanation(**payload,explanation_fingerprint=_hash(payload))


def validate_scenario_explanation_replay(explanation: ScenarioExplanation, **kwargs) -> bool:
    return build_scenario_explanation(**kwargs)==explanation


def validate_comparison_explanation_replay(explanation: ComparisonExplanation, *, comparison: MultiScenarioComparison, scenario_explanations: Sequence[ScenarioExplanation]) -> bool:
    return build_comparison_explanation(comparison=comparison,scenario_explanations=scenario_explanations)==explanation
