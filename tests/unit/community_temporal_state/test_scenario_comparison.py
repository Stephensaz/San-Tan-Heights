from dataclasses import fields
import pytest

from src.community_temporal_state.scenario_baseline import CertifiedScenarioBaseline
from src.community_temporal_state.scenario_evidence import ScenarioEvidenceSet
from src.community_temporal_state.scenario_pricing_timing import PricingPosition, ListingTiming, PricingTimingScenarioState
from src.community_temporal_state.scenario_buyer_substitution import (
    BuyerSubstitutionCompetitiveState, NumericDimensionPosition, CategoricalDimensionPosition
)
from src.community_temporal_state.scenario_new_construction import (
    NewConstructionScenarioState, NewConstructionNumericPosition, NewConstructionCategoricalPosition
)
from src.community_temporal_state.scenario_comparison import (
    ScenarioComparisonMember, ScenarioDimensionDifference, MultiScenarioComparison,
    build_comparison_member, compare_scenario_members, load_scenario_comparison_registry,
    validate_comparison_replay,
)

REGISTRY="registries/community_temporal_state/m13-006g-scenario-comparison-v1.0.yaml"

def registry(): return load_scenario_comparison_registry(REGISTRY)

def context(sid,fp):
    return CertifiedScenarioBaseline(
        scenario_id=sid,scenario_contract_fingerprint="a"*64,community_id="SAN-TAN-HEIGHTS",
        subject_id="PROPERTY-1",baseline_snapshot_id="SNAPSHOT-1",baseline_fingerprint="b"*64,
        facts=(),fact_source_fingerprints=("c"*64,),assumptions=(),pattern_applicability=(),
        unknowns=(f"{sid}-unknown",),limitations=("context limit",),context_fingerprint=fp
    )

def evidence(c,fp):
    return ScenarioEvidenceSet(
        evidence_set_id=f"E-{c.scenario_id}",scenario_id=c.scenario_id,
        scenario_context_fingerprint=c.context_fingerprint,temporal_ledger_fingerprint="d"*64,
        query_fingerprint="e"*64,included=(),excluded=(),source_fingerprints=(),evidence_fingerprints=(),
        unknowns=(),limitations=("evidence limit",),evidence_set_fingerprint=fp
    )

def dstate(c,e,price_pct,timing_days,fp):
    pp=PricingPosition(candidate_price=500000,reference_fact_key="reference_price",reference_price=500000,
        absolute_difference=0,percent_difference=price_pct,direction="SAME",position_fingerprint="1"*64)
    lt=ListingTiming(candidate_listing_date="2026-09-15",reference_fact_key="reference_date",
        reference_date="2026-09-01",day_difference=timing_days,direction="LATER_THAN_REFERENCE",timing_fingerprint="2"*64)
    return PricingTimingScenarioState(
        scenario_id=c.scenario_id,scenario_context_fingerprint=c.context_fingerprint,
        scenario_evidence_fingerprint=e.evidence_set_fingerprint,pricing_position=pp,listing_timing=lt,
        included_historical_evidence_count=0,excluded_historical_evidence_count=0,
        applicable_pattern_ids=("P1",),unknown_pattern_ids=(),evidence_source_fingerprints=(),
        unknowns=(),limitations=("D limit",),state_fingerprint=fp
    )

def num(name,v):
    return NumericDimensionPosition(dimension=name,candidate_value=v,reference_fact_key=f"ref_{name}",
        reference_value=v,absolute_difference=0,direction="SAME",position_fingerprint="3"*64)

def cat(name,v):
    return CategoricalDimensionPosition(dimension=name,candidate_value=v,reference_fact_key=f"ref_{name}",
        reference_value=v,relation="SAME",position_fingerprint="4"*64)

def estate(c,e,d,buyer,comp,resale,sub,scarcity,fp):
    return BuyerSubstitutionCompetitiveState(
        scenario_id=c.scenario_id,scenario_context_fingerprint=c.context_fingerprint,
        scenario_evidence_fingerprint=e.evidence_set_fingerprint,pricing_timing_state_fingerprint=d.state_fingerprint,
        buyer_depth=num("buyer_depth",buyer),comparable_depth=num("comparable_depth",comp),
        resale_competition=num("resale_competition",resale),substitution_requirement=cat("substitution_requirement",sub),
        scarcity_context=("scarcity_context",scarcity),included_historical_evidence_count=3,
        applicable_pattern_ids=("P1",),unknown_pattern_ids=(),unknowns=(),limitations=("E limit",),state_fingerprint=fp
    )

def fn(name,v):
    return NewConstructionNumericPosition(dimension=name,candidate_value=v,reference_fact_key=f"ref_{name}",
        reference_value=v,absolute_difference=0,direction="SAME",position_fingerprint="5"*64)

def fc(name,v):
    return NewConstructionCategoricalPosition(dimension=name,candidate_value=v,reference_fact_key=f"ref_{name}",
        reference_value=v,relation="SAME",position_fingerprint="6"*64)

def fstate(c,e,nc,inventory,incentive,posture,fp):
    return NewConstructionScenarioState(
        scenario_id=c.scenario_id,scenario_context_fingerprint=c.context_fingerprint,
        buyer_substitution_state_fingerprint=e.state_fingerprint,
        new_construction_competition=fn("new_construction_competition",nc),
        builder_inventory=fn("builder_inventory",inventory),
        builder_incentive_value=fn("builder_incentive_value",incentive),
        builder_incentive_posture=fc("builder_incentive_posture",posture),
        unknowns=(),limitations=("F limit",),state_fingerprint=fp
    )

def member(sid,order,base):
    c=context(sid,hex(base)[2:].rjust(64,"0"))
    ev=evidence(c,hex(base+1)[2:].rjust(64,"0"))
    d=dstate(c,ev,float(base),base,hex(base+2)[2:].rjust(64,"0"))
    e=estate(c,ev,d,float(base),float(base+1),float(base+2),f"S{base}",f"SC{base}",hex(base+3)[2:].rjust(64,"0"))
    f=fstate(c,e,float(base+3),float(base+4),float(base+5),f"POSTURE-{base}",hex(base+4)[2:].rjust(64,"0"))
    return build_comparison_member(user_order=order,context=c,evidence_set=ev,pricing_timing_state=d,buyer_substitution_state=e,new_construction_state=f,registry=registry())

def test_registry_frozen_and_guardrails():
    r=registry()
    assert r["status"]=="FROZEN" and r["ticket"]=="M13-006G"
    for key in ("no_ranking","no_winner","no_recommendation","no_hidden_score","no_weights","no_prediction","no_causal_inference","no_execution"):
        assert r["policy"][key] is True

def test_member_materializes_governed_dimensions():
    m=member("S1",0,10); d=dict(m.dimensions)
    assert d["pricing_position_percent"]==10.0
    assert d["listing_timing_days"]==10
    assert d["buyer_depth"]==10.0
    assert d["new_construction_competition"]==13.0
    assert d["applicable_patterns"]==("P1",)
    assert d["historical_evidence_count"]==3

def test_member_coverage_is_counts_not_score():
    m=member("S1",0,10)
    assert m.known_dimension_count>0
    assert m.total_dimension_count>=m.known_dimension_count
    assert not hasattr(m,"coverage_score")

def test_comparison_preserves_human_order():
    a=member("A",1,10); b=member("B",0,20)
    c=compare_scenario_members(comparison_id="C1",members=(a,b),registry=registry())
    assert c.scenario_ids==("B","A")

def test_unique_user_order_required():
    a=member("A",0,10); b=member("B",0,20)
    with pytest.raises(ValueError,match="unique user_order"):
        compare_scenario_members(comparison_id="C1",members=(a,b),registry=registry())

def test_unique_scenario_ids_required():
    a=member("A",0,10); b=member("A",1,20)
    with pytest.raises(ValueError,match="unique scenario ids"):
        compare_scenario_members(comparison_id="C1",members=(a,b),registry=registry())

def test_at_least_two_scenarios_required():
    with pytest.raises(ValueError,match="at least two"):
        compare_scenario_members(comparison_id="C1",members=(member("A",0,10),),registry=registry())

def test_numeric_relations_are_neutral():
    a=member("A",0,10); b=member("B",1,20)
    c=compare_scenario_members(comparison_id="C1",members=(a,b),registry=registry())
    row=next(x for x in c.pairwise_differences if x.dimension=="buyer_depth")
    assert row.relation=="LEFT_LOWER"

def test_categorical_relations_are_neutral():
    a=member("A",0,10); b=member("B",1,20)
    c=compare_scenario_members(comparison_id="C1",members=(a,b),registry=registry())
    row=next(x for x in c.pairwise_differences if x.dimension=="substitution_requirement")
    assert row.relation=="DIFFERENT"

def test_all_governed_dimensions_are_compared():
    a=member("A",0,10); b=member("B",1,20)
    c=compare_scenario_members(comparison_id="C1",members=(a,b),registry=registry())
    assert {x.dimension for x in c.pairwise_differences}==set(registry()["governed_dimensions"])

def test_three_scenarios_create_all_pairwise_comparisons():
    c=compare_scenario_members(comparison_id="C1",members=(member("A",0,10),member("B",1,20),member("C",2,30)),registry=registry())
    pairs={(x.left_scenario_id,x.right_scenario_id) for x in c.pairwise_differences}
    assert pairs=={("A","B"),("A","C"),("B","C")}

def test_unknowns_and_limitations_are_visible():
    a=member("A",0,10); b=member("B",1,20)
    c=compare_scenario_members(comparison_id="C1",members=(a,b),registry=registry())
    assert "A-unknown" in c.unknowns and "B-unknown" in c.unknowns
    assert any("do not indicate preference" in x for x in c.limitations)

def test_context_evidence_lineage_enforced():
    c=context("S1","a"*64); ev=evidence(c,"b"*64)
    bad=ScenarioEvidenceSet(**{**ev.__dict__,"scenario_context_fingerprint":"9"*64})
    d=dstate(c,ev,1,1,"c"*64); e=estate(c,ev,d,1,1,1,"L","N","d"*64); f=fstate(c,e,1,1,1,"P","e"*64)
    with pytest.raises(ValueError,match="context/evidence"):
        build_comparison_member(user_order=0,context=c,evidence_set=bad,pricing_timing_state=d,buyer_substitution_state=e,new_construction_state=f,registry=registry())

def test_d_e_lineage_enforced():
    c=context("S1","a"*64); ev=evidence(c,"b"*64); d=dstate(c,ev,1,1,"c"*64)
    e=estate(c,ev,d,1,1,1,"L","N","d"*64)
    e=BuyerSubstitutionCompetitiveState(**{**e.__dict__,"pricing_timing_state_fingerprint":"9"*64})
    f=fstate(c,e,1,1,1,"P","e"*64)
    with pytest.raises(ValueError,match="D/E"):
        build_comparison_member(user_order=0,context=c,evidence_set=ev,pricing_timing_state=d,buyer_substitution_state=e,new_construction_state=f,registry=registry())

def test_e_f_lineage_enforced():
    c=context("S1","a"*64); ev=evidence(c,"b"*64); d=dstate(c,ev,1,1,"c"*64); e=estate(c,ev,d,1,1,1,"L","N","d"*64)
    f=fstate(c,e,1,1,1,"P","e"*64)
    f=NewConstructionScenarioState(**{**f.__dict__,"buyer_substitution_state_fingerprint":"9"*64})
    with pytest.raises(ValueError,match="E/F"):
        build_comparison_member(user_order=0,context=c,evidence_set=ev,pricing_timing_state=d,buyer_substitution_state=e,new_construction_state=f,registry=registry())

def test_comparison_is_deterministic_and_replayable():
    members=(member("A",0,10),member("B",1,20))
    c=compare_scenario_members(comparison_id="C1",members=members,registry=registry())
    assert c==compare_scenario_members(comparison_id="C1",members=members,registry=registry())
    assert validate_comparison_replay(c,members=members,registry=registry())

def test_no_rank_winner_score_recommendation_or_execution_fields():
    forbidden={"rank","winner","score","utility_score","weights","recommended_scenario","recommended_action","prediction","execute","execution_state"}
    for cls in (ScenarioComparisonMember,ScenarioDimensionDifference,MultiScenarioComparison):
        assert {x.name for x in fields(cls)}.isdisjoint(forbidden)
