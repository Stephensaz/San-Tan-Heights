from dataclasses import fields
import pytest

from src.community_temporal_state.scenario_baseline import CertifiedScenarioBaseline
from src.community_temporal_state.scenario_buyer_substitution import BuyerSubstitutionCompetitiveState
from src.community_temporal_state.scenario_new_construction import (
    NewConstructionCategoricalPosition,
    NewConstructionNumericPosition,
    NewConstructionScenarioState,
    build_new_construction_scenario_state,
    load_new_construction_registry,
    validate_new_construction_state_replay,
)

REGISTRY="registries/community_temporal_state/m13-006f-new-construction-v1.0.yaml"


def registry():
    return load_new_construction_registry(REGISTRY)


def context(*,facts=None,assumptions=None,fp="a"*64):
    return CertifiedScenarioBaseline(
        scenario_id="SCENARIO-1",scenario_contract_fingerprint="b"*64,
        community_id="SAN-TAN-HEIGHTS",subject_id="PROPERTY-1",
        baseline_snapshot_id="SNAPSHOT-1",baseline_fingerprint="c"*64,
        facts=tuple(sorted((facts or {
            "current_new_construction_competition":5,
            "current_builder_inventory":12,
            "current_builder_incentive_value":15000,
            "current_builder_incentive_posture":"MODERATE",
        }).items())),
        fact_source_fingerprints=("d"*64,),
        assumptions=tuple(sorted((assumptions or {
            "candidate_new_construction_competition":7,
            "candidate_builder_inventory":18,
            "candidate_builder_incentive_value":20000,
            "candidate_builder_incentive_posture":"HIGH",
        }).items())),
        pattern_applicability=(),unknowns=("one context unknown",),
        limitations=("Certified context only.",),context_fingerprint=fp,
    )


def estate(c=None,*,scenario_id="SCENARIO-1",context_fp=None):
    c=c or context()
    return BuyerSubstitutionCompetitiveState(
        scenario_id=scenario_id,
        scenario_context_fingerprint=context_fp or c.context_fingerprint,
        scenario_evidence_fingerprint="e"*64,
        pricing_timing_state_fingerprint="f"*64,
        buyer_depth=None,comparable_depth=None,resale_competition=None,
        substitution_requirement=None,scarcity_context=None,
        included_historical_evidence_count=0,applicable_pattern_ids=(),unknown_pattern_ids=(),
        unknowns=("e-state unknown",),limitations=("E descriptive only.",),state_fingerprint="1"*64,
    )


def build(c=None,e=None):
    c=c or context(); e=e or estate(c)
    return build_new_construction_scenario_state(context=c,buyer_substitution_state=e,registry=registry())


def test_registry_frozen_and_boundaries():
    r=registry()
    assert r["status"]=="FROZEN" and r["ticket"]=="M13-006F"
    for key in ("no_prediction","no_recommendation","no_ranking","no_hidden_score","no_causal_inference","no_execution"):
        assert r["policy"][key] is True


def test_competition_difference_descriptive():
    p=build().new_construction_competition
    assert p.candidate_value==7.0 and p.reference_value==5.0
    assert p.absolute_difference==2.0 and p.direction=="ABOVE_REFERENCE"


def test_inventory_difference_descriptive():
    p=build().builder_inventory
    assert p.candidate_value==18.0 and p.reference_value==12.0
    assert p.absolute_difference==6.0


def test_incentive_value_difference_descriptive():
    p=build().builder_incentive_value
    assert p.candidate_value==20000.0 and p.reference_value==15000.0
    assert p.absolute_difference==5000.0


def test_incentive_posture_relation_neutral():
    p=build().builder_incentive_posture
    assert p.candidate_value=="HIGH" and p.reference_value=="MODERATE"
    assert p.relation=="DIFFERENT"


def test_same_values_described_as_same():
    c=context(assumptions={
        "candidate_new_construction_competition":5,
        "candidate_builder_inventory":12,
        "candidate_builder_incentive_value":15000,
        "candidate_builder_incentive_posture":"MODERATE",
    })
    r=build(c)
    assert r.new_construction_competition.direction=="SAME"
    assert r.builder_inventory.direction=="SAME"
    assert r.builder_incentive_value.direction=="SAME"
    assert r.builder_incentive_posture.relation=="SAME"


@pytest.mark.parametrize("key,unknown",[
    ("candidate_new_construction_competition","EXPLICIT_NEW_CONSTRUCTION_COMPETITION_ASSUMPTION_NOT_PROVIDED"),
    ("candidate_builder_inventory","EXPLICIT_BUILDER_INVENTORY_ASSUMPTION_NOT_PROVIDED"),
    ("candidate_builder_incentive_value","EXPLICIT_BUILDER_INCENTIVE_VALUE_ASSUMPTION_NOT_PROVIDED"),
    ("candidate_builder_incentive_posture","EXPLICIT_BUILDER_INCENTIVE_POSTURE_ASSUMPTION_NOT_PROVIDED"),
])
def test_missing_assumptions_are_explicit_unknowns(key,unknown):
    assumptions=dict(context().assumptions); assumptions.pop(key)
    r=build(context(assumptions=assumptions))
    assert unknown in r.unknowns


def test_missing_reference_is_explicit_unknown():
    facts=dict(context().facts); facts.pop("current_builder_inventory")
    r=build(context(facts=facts))
    assert r.builder_inventory is None
    assert "CERTIFIED_BUILDER_INVENTORY_REFERENCE_NOT_AVAILABLE" in r.unknowns


@pytest.mark.parametrize("value",[-1,True,"seven"])
def test_invalid_numeric_assumption_rejected(value):
    assumptions=dict(context().assumptions); assumptions["candidate_builder_inventory"]=value
    with pytest.raises(ValueError,match="builder_inventory candidate"):
        build(context(assumptions=assumptions))


def test_invalid_posture_assumption_rejected():
    assumptions=dict(context().assumptions); assumptions["candidate_builder_incentive_posture"]=""
    with pytest.raises(ValueError,match="posture candidate"):
        build(context(assumptions=assumptions))


def test_scenario_identity_mismatch_rejected():
    c=context()
    with pytest.raises(ValueError,match="scenario identity mismatch"):
        build(c,estate(c,scenario_id="OTHER"))


def test_context_lineage_mismatch_rejected():
    c=context()
    with pytest.raises(ValueError,match="lineage mismatch"):
        build(c,estate(c,context_fp="9"*64))


def test_unknowns_and_limitations_carry_forward():
    r=build()
    assert "one context unknown" in r.unknowns and "e-state unknown" in r.unknowns
    assert any("not builder-behavior forecasts or strategy recommendations" in x for x in r.limitations)


def test_state_deterministic_and_replayable():
    c=context();e=estate(c);a=build(c,e)
    assert a==build(c,e)
    assert validate_new_construction_state_replay(a,context=c,buyer_substitution_state=e,registry=registry())


def test_no_prediction_recommendation_ranking_or_execution_fields():
    forbidden={"prediction","sale_probability","recommended_action","recommended_strategy","rank","winner","utility_score","seller_score","execute","execution_state","causal_effect"}
    for cls in (NewConstructionNumericPosition,NewConstructionCategoricalPosition,NewConstructionScenarioState):
        assert {x.name for x in fields(cls)}.isdisjoint(forbidden)
