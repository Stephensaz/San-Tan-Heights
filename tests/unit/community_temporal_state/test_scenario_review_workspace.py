from dataclasses import fields, replace
import pytest

from src.community_temporal_state.scenario_baseline import CertifiedScenarioBaseline, PatternApplicability
from src.community_temporal_state.scenario_evidence import ScenarioEvidenceSet
from src.community_temporal_state.scenario_pricing_timing import build_pricing_timing_scenario_state, load_pricing_timing_registry
from src.community_temporal_state.scenario_buyer_substitution import build_buyer_substitution_competitive_state, load_buyer_substitution_registry
from src.community_temporal_state.scenario_new_construction import build_new_construction_scenario_state, load_new_construction_registry
from src.community_temporal_state.scenario_comparison import build_comparison_member, compare_scenario_members, load_scenario_comparison_registry
from src.community_temporal_state.scenario_explainability import build_scenario_explanation, build_comparison_explanation, load_explainability_registry
from src.community_temporal_state.scenario_review_workspace import (
    ScenarioReviewItem, ScenarioReviewPackage, build_review_item,
    assemble_review_package, load_review_workspace_registry,
    validate_review_package_replay,
)

DREG="registries/community_temporal_state/m13-006d-pricing-timing-v1.0.yaml"
EREG="registries/community_temporal_state/m13-006e-buyer-substitution-v1.0.yaml"
FREG="registries/community_temporal_state/m13-006f-new-construction-v1.0.yaml"
GREG="registries/community_temporal_state/m13-006g-scenario-comparison-v1.0.yaml"
HREG="registries/community_temporal_state/m13-006h-explainability-v1.0.yaml"
IREG="registries/community_temporal_state/m13-006i-review-workspace-v1.0.yaml"


def pattern(pid="P1"):
    return PatternApplicability(
        pattern_id=pid,pattern_fingerprint="1"*64,pattern_domain="pricing",
        pattern_statement="Historical descriptive association.",state="APPLICABLE",
        reason_codes=("GOVERNED_RULE_SATISFIED",),matched_fact_keys=("phase",),
        matched_assumption_keys=("candidate_list_price",),source_ledger_fingerprint="2"*64,
        limitations=("Historical association only.",),applicability_fingerprint="3"*64,
    )


def context(sid,fp,subject_id="PROPERTY-1",community_id="SAN-TAN-HEIGHTS"):
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
        scenario_id=sid,scenario_contract_fingerprint="b"*64,community_id=community_id,
        subject_id=subject_id,baseline_snapshot_id="SNAPSHOT-1",baseline_fingerprint="c"*64,
        facts=tuple(sorted(facts.items())),fact_source_fingerprints=("d"*64,),
        assumptions=tuple(sorted(assumptions.items())),pattern_applicability=(pattern(),),
        unknowns=(f"{sid}-unknown",),limitations=("Certified context only.",),context_fingerprint=fp
    )


def evidence(c,fp):
    return ScenarioEvidenceSet(
        evidence_set_id=f"E-{c.scenario_id}",scenario_id=c.scenario_id,
        scenario_context_fingerprint=c.context_fingerprint,temporal_ledger_fingerprint="f"*64,
        query_fingerprint="4"*64,included=(),excluded=(),source_fingerprints=("5"*64,),
        evidence_fingerprints=("6"*64,),unknowns=("historical sample thin",),
        limitations=("Historical evidence descriptive.",),evidence_set_fingerprint=fp
    )


def bundle(sid,order,context_fp,evidence_fp,subject_id="PROPERTY-1",community_id="SAN-TAN-HEIGHTS"):
    c=context(sid,context_fp,subject_id=subject_id,community_id=community_id)
    ev=evidence(c,evidence_fp)
    d=build_pricing_timing_scenario_state(context=c,evidence_set=ev,registry=load_pricing_timing_registry(DREG))
    e=build_buyer_substitution_competitive_state(context=c,evidence_set=ev,pricing_timing_state=d,registry=load_buyer_substitution_registry(EREG))
    f=build_new_construction_scenario_state(context=c,buyer_substitution_state=e,registry=load_new_construction_registry(FREG))
    g=build_comparison_member(user_order=order,context=c,evidence_set=ev,pricing_timing_state=d,buyer_substitution_state=e,new_construction_state=f,registry=load_scenario_comparison_registry(GREG))
    h=build_scenario_explanation(context=c,evidence_set=ev,pricing_timing_state=d,buyer_substitution_state=e,new_construction_state=f,comparison_member=g,registry=load_explainability_registry(HREG))
    return c,ev,d,e,f,g,h


def package(human_decisions=()):
    a=bundle("A",0,"a"*64,"e"*64)
    b=bundle("B",1,"7"*64,"8"*64)
    comp=compare_scenario_members(comparison_id="COMP-1",members=(a[5],b[5]),registry=load_scenario_comparison_registry(GREG))
    cex=build_comparison_explanation(comparison=comp,scenario_explanations=(a[6],b[6]))
    pkg=assemble_review_package(
        package_id="PKG-1",community_id="SAN-TAN-HEIGHTS",subject_id="PROPERTY-1",
        contexts=(a[0],b[0]),members=(a[5],b[5]),scenario_explanations=(a[6],b[6]),
        comparison=comp,comparison_explanation=cex,registry=load_review_workspace_registry(IREG),
        human_decisions=human_decisions,
    )
    return a,b,comp,cex,pkg


def test_registry_frozen_and_guardrails():
    r=load_review_workspace_registry(IREG)
    assert r["status"]=="FROZEN" and r["ticket"]=="M13-006I"
    for key in ("no_automatic_selection","no_recommendation","no_ranking","no_winner","no_hidden_score","no_execution","no_publication"):
        assert r["policy"][key] is True


def test_review_item_keeps_facts_and_assumptions_separate():
    a,*_=bundle("A",0,"a"*64,"e"*64)
    b=bundle("A",0,"a"*64,"e"*64)
    item=build_review_item(context=b[0],comparison_member=b[5],explanation=b[6])
    assert item.facts==b[0].facts
    assert item.assumptions==b[0].assumptions
    assert set(k for k,_ in item.facts).isdisjoint(k for k,_ in item.assumptions)


def test_review_item_contains_outputs_changes_and_evidence():
    b=bundle("A",0,"a"*64,"e"*64)
    item=build_review_item(context=b[0],comparison_member=b[5],explanation=b[6])
    assert item.scenario_outputs
    assert "pricing_position" in item.changed_from_reference
    assert item.evidence_source_fingerprints==("5"*64,)
    assert item.evidence_fingerprints==("6"*64,)


def test_package_is_ready_for_human_review_only():
    *_,pkg=package()
    assert pkg.review_state=="READY_FOR_HUMAN_REVIEW"
    assert any("human review only" in x for x in pkg.limitations)


def test_package_preserves_human_scenario_order():
    *_,pkg=package()
    assert pkg.scenario_ids==("A","B")
    assert tuple(x.scenario_id for x in pkg.review_items)==("A","B")
    assert tuple(x.user_order for x in pkg.review_items)==(0,1)


def test_certified_inputs_are_explicit():
    a,b,comp,cex,pkg=package()
    assert comp.comparison_fingerprint in pkg.certified_inputs
    assert cex.explanation_fingerprint in pkg.certified_inputs
    assert a[0].context_fingerprint in pkg.certified_inputs
    assert b[6].explanation_fingerprint in pkg.certified_inputs


def test_evidence_is_aggregated_without_interpretation():
    *_,pkg=package()
    assert "5"*64 in pkg.evidence
    assert "6"*64 in pkg.evidence


def test_human_decisions_are_recorded_only_when_supplied():
    *_,empty=package()
    assert empty.human_decisions==()
    *_,with_decision=package(("Seller will review both scenarios.",))
    assert with_decision.human_decisions==("Seller will review both scenarios.",)


def test_context_member_lineage_mismatch_rejected():
    b=bundle("A",0,"a"*64,"e"*64)
    bad=replace(b[5],scenario_context_fingerprint="9"*64)
    with pytest.raises(ValueError,match="context/member lineage mismatch"):
        build_review_item(context=b[0],comparison_member=bad,explanation=b[6])


def test_facts_must_match_certified_context():
    b=bundle("A",0,"a"*64,"e"*64)
    bad=replace(b[6],facts=(("fake_fact",1),))
    with pytest.raises(ValueError,match="facts must match certified context"):
        build_review_item(context=b[0],comparison_member=b[5],explanation=bad)


def test_package_requires_exact_one_item_per_scenario():
    a,b,comp,cex,_=package()
    with pytest.raises(ValueError,match="exactly one A-H item"):
        assemble_review_package(
            package_id="PKG-2",community_id="SAN-TAN-HEIGHTS",subject_id="PROPERTY-1",
            contexts=(a[0],),members=(a[5],b[5]),scenario_explanations=(a[6],b[6]),
            comparison=comp,comparison_explanation=cex,registry=load_review_workspace_registry(IREG),
        )


def test_comparison_explanation_order_must_match():
    a,b,comp,cex,_=package()
    bad=replace(cex,scenario_ids=("B","A"))
    with pytest.raises(ValueError,match="scenario order mismatch"):
        assemble_review_package(
            package_id="PKG-2",community_id="SAN-TAN-HEIGHTS",subject_id="PROPERTY-1",
            contexts=(a[0],b[0]),members=(a[5],b[5]),scenario_explanations=(a[6],b[6]),
            comparison=comp,comparison_explanation=bad,registry=load_review_workspace_registry(IREG),
        )


def test_community_subject_mismatch_rejected():
    a=bundle("A",0,"a"*64,"e"*64)
    b=bundle("B",1,"7"*64,"8"*64,subject_id="PROPERTY-2")
    comp=compare_scenario_members(comparison_id="COMP-1",members=(a[5],b[5]),registry=load_scenario_comparison_registry(GREG))
    cex=build_comparison_explanation(comparison=comp,scenario_explanations=(a[6],b[6]))
    with pytest.raises(ValueError,match="community/subject mismatch"):
        assemble_review_package(
            package_id="PKG-2",community_id="SAN-TAN-HEIGHTS",subject_id="PROPERTY-1",
            contexts=(a[0],b[0]),members=(a[5],b[5]),scenario_explanations=(a[6],b[6]),
            comparison=comp,comparison_explanation=cex,registry=load_review_workspace_registry(IREG),
        )


def test_package_is_deterministic_and_replayable():
    a,b,comp,cex,pkg=package(("Seller chooses after review.",))
    assert validate_review_package_replay(
        pkg,package_id="PKG-1",community_id="SAN-TAN-HEIGHTS",subject_id="PROPERTY-1",
        contexts=(a[0],b[0]),members=(a[5],b[5]),scenario_explanations=(a[6],b[6]),
        comparison=comp,comparison_explanation=cex,registry=load_review_workspace_registry(IREG),
        human_decisions=("Seller chooses after review.",),
    )


def test_no_auto_selection_rank_approval_authority_or_execution_fields():
    forbidden={
        "selected_scenario","recommended_scenario","rank","winner","score","utility_score",
        "approved","approval","authority","authorized","execute","execution_state","published",
    }
    for cls in (ScenarioReviewItem,ScenarioReviewPackage):
        assert {x.name for x in fields(cls)}.isdisjoint(forbidden)
