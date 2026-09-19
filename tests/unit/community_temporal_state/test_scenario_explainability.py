from dataclasses import fields, replace
import pytest

from src.community_temporal_state.scenario_baseline import CertifiedScenarioBaseline, PatternApplicability
from src.community_temporal_state.scenario_evidence import ScenarioEvidenceSet
from src.community_temporal_state.scenario_pricing_timing import build_pricing_timing_scenario_state, load_pricing_timing_registry
from src.community_temporal_state.scenario_buyer_substitution import build_buyer_substitution_competitive_state, load_buyer_substitution_registry
from src.community_temporal_state.scenario_new_construction import build_new_construction_scenario_state, load_new_construction_registry
from src.community_temporal_state.scenario_comparison import build_comparison_member, compare_scenario_members, load_scenario_comparison_registry
from src.community_temporal_state.scenario_explainability import (
    ScenarioExplanation, ComparisonExplanation, build_scenario_explanation,
    build_comparison_explanation, load_explainability_registry,
    validate_scenario_explanation_replay, validate_comparison_explanation_replay,
)

DREG="registries/community_temporal_state/m13-006d-pricing-timing-v1.0.yaml"
EREG="registries/community_temporal_state/m13-006e-buyer-substitution-v1.0.yaml"
FREG="registries/community_temporal_state/m13-006f-new-construction-v1.0.yaml"
GREG="registries/community_temporal_state/m13-006g-scenario-comparison-v1.0.yaml"
HREG="registries/community_temporal_state/m13-006h-explainability-v1.0.yaml"


def pattern(pid="P1",state="APPLICABLE"):
    return PatternApplicability(
        pattern_id=pid,pattern_fingerprint="1"*64,pattern_domain="pricing",
        pattern_statement="Historical association.",state=state,
        reason_codes=("GOVERNED_RULE_SATISFIED",),matched_fact_keys=("phase",),
        matched_assumption_keys=("candidate_list_price",),source_ledger_fingerprint="2"*64,
        limitations=("Historical association only.",),applicability_fingerprint="3"*64,
    )


def context(sid="S1",fp="a"*64):
    facts={
        "reference_price":500000,"reference_date":"2026-09-01",
        "current_buyer_depth":4,"current_comparable_depth":6,"current_resale_competition":5,
        "current_substitution_requirement":"LOW","scarcity_context":"NORMAL",
        "current_new_construction_competition":3,"current_builder_inventory":10,
        "current_builder_incentive_value":15000,"current_builder_incentive_posture":"MODERATE",
    }
    assumptions={
        "candidate_list_price":525000,"candidate_listing_date":"2026-09-15",
        "candidate_buyer_depth":3,"candidate_comparable_depth":8,"candidate_resale_competition":7,
        "candidate_substitution_requirement":"MODERATE",
        "candidate_new_construction_competition":5,"candidate_builder_inventory":14,
        "candidate_builder_incentive_value":20000,"candidate_builder_incentive_posture":"HIGH",
    }
    return CertifiedScenarioBaseline(
        scenario_id=sid,scenario_contract_fingerprint="b"*64,community_id="SAN-TAN-HEIGHTS",
        subject_id="PROPERTY-1",baseline_snapshot_id="SNAPSHOT-1",baseline_fingerprint="c"*64,
        facts=tuple(sorted(facts.items())),fact_source_fingerprints=("d"*64,),
        assumptions=tuple(sorted(assumptions.items())),pattern_applicability=(pattern(),),
        unknowns=("pool status unknown",),limitations=("Certified context limit.",),context_fingerprint=fp
    )


def evidence(c,fp="e"*64):
    return ScenarioEvidenceSet(
        evidence_set_id=f"E-{c.scenario_id}",scenario_id=c.scenario_id,
        scenario_context_fingerprint=c.context_fingerprint,temporal_ledger_fingerprint="f"*64,
        query_fingerprint="4"*64,included=(),excluded=(),source_fingerprints=("5"*64,),
        evidence_fingerprints=("6"*64,),unknowns=("historical sample thin",),
        limitations=("Historical evidence descriptive.",),evidence_set_fingerprint=fp
    )


def bundle(sid="S1",order=0,context_fp="a"*64,evidence_fp="e"*64):
    c=context(sid,context_fp); ev=evidence(c,evidence_fp)
    d=build_pricing_timing_scenario_state(context=c,evidence_set=ev,registry=load_pricing_timing_registry(DREG))
    e=build_buyer_substitution_competitive_state(context=c,evidence_set=ev,pricing_timing_state=d,registry=load_buyer_substitution_registry(EREG))
    f=build_new_construction_scenario_state(context=c,buyer_substitution_state=e,registry=load_new_construction_registry(FREG))
    g=build_comparison_member(user_order=order,context=c,evidence_set=ev,pricing_timing_state=d,buyer_substitution_state=e,new_construction_state=f,registry=load_scenario_comparison_registry(GREG))
    h=build_scenario_explanation(context=c,evidence_set=ev,pricing_timing_state=d,buyer_substitution_state=e,new_construction_state=f,comparison_member=g,registry=load_explainability_registry(HREG))
    return c,ev,d,e,f,g,h


def test_registry_frozen_and_boundaries():
    r=load_explainability_registry(HREG)
    assert r["status"]=="FROZEN" and r["ticket"]=="M13-006H"
    for key in ("no_prediction","no_recommendation","no_ranking","no_winner","no_hidden_score","no_invented_confidence","no_causal_inference","no_execution"):
        assert r["policy"][key] is True


def test_facts_and_assumptions_remain_separate():
    c,_,_,_,_,_,h=bundle()
    assert h.facts==c.facts
    assert h.assumptions==c.assumptions
    assert set(k for k,_ in h.facts).isdisjoint(k for k,_ in h.assumptions)


def test_changed_from_reference_is_explicit():
    *_,h=bundle()
    assert "pricing_position" in h.changed_from_reference
    assert "listing_timing" in h.changed_from_reference
    assert "buyer_depth" in h.changed_from_reference
    assert "new_construction_competition" in h.changed_from_reference


def test_evidence_lineage_is_explicit():
    _,ev,_,_,_,_,h=bundle()
    assert h.evidence_source_fingerprints==ev.source_fingerprints
    assert h.evidence_fingerprints==ev.evidence_fingerprints


def test_applicable_patterns_are_explicit():
    *_,h=bundle()
    assert h.applicable_pattern_ids==("P1",)


def test_unknowns_and_limitations_are_visible():
    *_,h=bundle()
    assert "pool status unknown" in h.unknowns
    assert "historical sample thin" in h.unknowns
    assert any("not predictions" in x for x in h.limitations)
    assert any("Assumptions remain assumptions" in x for x in h.limitations)


def test_g_lineage_mismatch_is_rejected():
    c,ev,d,e,f,g,_=bundle()
    bad=replace(g,scenario_context_fingerprint="9"*64)
    with pytest.raises(ValueError,match="context/G lineage"):
        build_scenario_explanation(context=c,evidence_set=ev,pricing_timing_state=d,buyer_substitution_state=e,new_construction_state=f,comparison_member=bad,registry=load_explainability_registry(HREG))


def test_scenario_identity_mismatch_is_rejected():
    c,ev,d,e,f,g,_=bundle()
    bad=replace(g,scenario_id="OTHER")
    with pytest.raises(ValueError,match="scenario identity mismatch"):
        build_scenario_explanation(context=c,evidence_set=ev,pricing_timing_state=d,buyer_substitution_state=e,new_construction_state=f,comparison_member=bad,registry=load_explainability_registry(HREG))


def test_comparison_explanation_preserves_pairwise_differences():
    a=bundle("A",0,"a"*64,"e"*64)
    b=bundle("B",1,"7"*64,"8"*64)
    comp=compare_scenario_members(comparison_id="C1",members=(a[5],b[5]),registry=load_scenario_comparison_registry(GREG))
    ex=build_comparison_explanation(comparison=comp,scenario_explanations=(a[6],b[6]))
    assert len(ex.pairwise_differences)==len(comp.pairwise_differences)
    assert ex.scenario_ids==("A","B")


def test_comparison_requires_exact_explanation_set():
    a=bundle("A",0,"a"*64,"e"*64)
    b=bundle("B",1,"7"*64,"8"*64)
    comp=compare_scenario_members(comparison_id="C1",members=(a[5],b[5]),registry=load_scenario_comparison_registry(GREG))
    with pytest.raises(ValueError,match="exactly one explanation"):
        build_comparison_explanation(comparison=comp,scenario_explanations=(a[6],))


def test_scenario_explanation_deterministic_and_replayable():
    c,ev,d,e,f,g,h=bundle()
    assert validate_scenario_explanation_replay(h,context=c,evidence_set=ev,pricing_timing_state=d,buyer_substitution_state=e,new_construction_state=f,comparison_member=g,registry=load_explainability_registry(HREG))


def test_comparison_explanation_deterministic_and_replayable():
    a=bundle("A",0,"a"*64,"e"*64); b=bundle("B",1,"7"*64,"8"*64)
    comp=compare_scenario_members(comparison_id="C1",members=(a[5],b[5]),registry=load_scenario_comparison_registry(GREG))
    ex=build_comparison_explanation(comparison=comp,scenario_explanations=(a[6],b[6]))
    assert validate_comparison_explanation_replay(ex,comparison=comp,scenario_explanations=(a[6],b[6]))


def test_no_decision_prediction_confidence_or_execution_fields():
    forbidden={"rank","winner","score","utility_score","recommended_action","recommended_scenario","prediction","confidence","causal_effect","execute","execution_state"}
    for cls in (ScenarioExplanation,ComparisonExplanation):
        assert {x.name for x in fields(cls)}.isdisjoint(forbidden)
