from dataclasses import fields, replace

import pytest

from src.community_temporal_state.scenario_baseline import CertifiedScenarioBaseline, PatternApplicability
from src.community_temporal_state.scenario_buyer_substitution import (
    BuyerSubstitutionCompetitiveState,
    CategoricalDimensionPosition,
    NumericDimensionPosition,
    build_buyer_substitution_competitive_state,
    load_buyer_substitution_registry,
    validate_buyer_substitution_state_replay,
)
from src.community_temporal_state.scenario_evidence import ScenarioEvidenceSet
from src.community_temporal_state.scenario_pricing_timing import PricingTimingScenarioState

REGISTRY="registries/community_temporal_state/m13-006e-buyer-substitution-v1.0.yaml"


def registry():
    return load_buyer_substitution_registry(REGISTRY)


def pattern(state="APPLICABLE",pattern_id="P1"):
    return PatternApplicability(
        pattern_id=pattern_id,pattern_fingerprint="1"*64,pattern_domain="buyer_depth",
        pattern_statement="Historical descriptive association.",state=state,
        reason_codes=("GOVERNED_RULE_SATISFIED",),matched_fact_keys=("phase",),
        matched_assumption_keys=("candidate_buyer_depth",),source_ledger_fingerprint="2"*64,
        limitations=("Historical association only.",),applicability_fingerprint="3"*64,
    )


def context(*,facts=None,assumptions=None,patterns=None,fp="a"*64):
    return CertifiedScenarioBaseline(
        scenario_id="SCENARIO-1",scenario_contract_fingerprint="b"*64,
        community_id="SAN-TAN-HEIGHTS",subject_id="PROPERTY-1",
        baseline_snapshot_id="SNAPSHOT-1",baseline_fingerprint="c"*64,
        facts=tuple(sorted((facts or {
            "current_buyer_depth":4,
            "current_comparable_depth":6,
            "current_resale_competition":5,
            "current_substitution_requirement":"LOW",
            "scarcity_context":"NORMAL",
        }).items())),
        fact_source_fingerprints=("d"*64,),
        assumptions=tuple(sorted((assumptions or {
            "candidate_buyer_depth":3,
            "candidate_comparable_depth":8,
            "candidate_resale_competition":7,
            "candidate_substitution_requirement":"MODERATE",
        }).items())),
        pattern_applicability=tuple(patterns or (pattern(),)),
        unknowns=("pool status unknown",),limitations=("Certified point-in-time context.",),
        context_fingerprint=fp,
    )


def evidence(c=None,*,scenario_id="SCENARIO-1",context_fp=None):
    c=c or context()
    return ScenarioEvidenceSet(
        evidence_set_id="ESET-1",scenario_id=scenario_id,
        scenario_context_fingerprint=context_fp or c.context_fingerprint,
        temporal_ledger_fingerprint="e"*64,query_fingerprint="f"*64,
        included=(),excluded=(),source_fingerprints=("4"*64,),evidence_fingerprints=("5"*64,),
        unknowns=("historical sample thin",),limitations=("Historical evidence is descriptive.",),
        evidence_set_fingerprint="6"*64,
    )


def dstate(c=None,e=None,*,scenario_id="SCENARIO-1",context_fp=None,evidence_fp=None):
    c=c or context()
    e=e or evidence(c)
    return PricingTimingScenarioState(
        scenario_id=scenario_id,
        scenario_context_fingerprint=context_fp or c.context_fingerprint,
        scenario_evidence_fingerprint=evidence_fp or e.evidence_set_fingerprint,
        pricing_position=None,listing_timing=None,
        included_historical_evidence_count=0,excluded_historical_evidence_count=0,
        applicable_pattern_ids=("P1",),unknown_pattern_ids=(),
        evidence_source_fingerprints=("4"*64,),
        unknowns=("pricing input not modeled",),
        limitations=("Pricing/timing descriptive only.",),
        state_fingerprint="7"*64,
    )


def build(c=None,e=None,d=None):
    c=c or context()
    e=e or evidence(c)
    d=d or dstate(c,e)
    return build_buyer_substitution_competitive_state(
        context=c,evidence_set=e,pricing_timing_state=d,registry=registry()
    )


def test_registry_frozen_and_prohibitions_enabled():
    r=registry()
    assert r["status"]=="FROZEN" and r["ticket"]=="M13-006E"
    for key in ("no_prediction","no_recommendation","no_ranking","no_hidden_score","no_causal_inference","no_execution"):
        assert r["policy"][key] is True


def test_buyer_depth_difference_is_descriptive():
    p=build().buyer_depth
    assert p.candidate_value==3.0 and p.reference_value==4.0
    assert p.absolute_difference==-1.0 and p.direction=="BELOW_REFERENCE"


def test_comparable_depth_difference_is_descriptive():
    p=build().comparable_depth
    assert p.candidate_value==8.0 and p.reference_value==6.0
    assert p.absolute_difference==2.0 and p.direction=="ABOVE_REFERENCE"


def test_resale_competition_difference_is_descriptive():
    p=build().resale_competition
    assert p.candidate_value==7.0 and p.reference_value==5.0
    assert p.absolute_difference==2.0


def test_substitution_change_is_neutral_relation():
    p=build().substitution_requirement
    assert p.reference_value=="LOW" and p.candidate_value=="MODERATE"
    assert p.relation=="DIFFERENT"


def test_scarcity_context_is_preserved_not_scored():
    assert build().scarcity_context==("scarcity_context","NORMAL")


def test_missing_buyer_depth_assumption_yields_unknown():
    c=context(assumptions={
        "candidate_comparable_depth":8,
        "candidate_resale_competition":7,
        "candidate_substitution_requirement":"MODERATE",
    })
    r=build(c)
    assert r.buyer_depth is None
    assert "EXPLICIT_BUYER_DEPTH_ASSUMPTION_NOT_PROVIDED" in r.unknowns


def test_missing_buyer_depth_reference_yields_unknown():
    c=context(facts={
        "current_comparable_depth":6,"current_resale_competition":5,
        "current_substitution_requirement":"LOW","scarcity_context":"NORMAL",
    })
    r=build(c)
    assert r.buyer_depth is None
    assert "CERTIFIED_BUYER_DEPTH_REFERENCE_NOT_AVAILABLE" in r.unknowns


def test_missing_substitution_assumption_yields_unknown():
    c=context(assumptions={
        "candidate_buyer_depth":3,"candidate_comparable_depth":8,"candidate_resale_competition":7,
    })
    r=build(c)
    assert r.substitution_requirement is None
    assert "EXPLICIT_SUBSTITUTION_REQUIREMENT_ASSUMPTION_NOT_PROVIDED" in r.unknowns


def test_missing_scarcity_context_yields_unknown():
    c=context(facts={
        "current_buyer_depth":4,"current_comparable_depth":6,
        "current_resale_competition":5,"current_substitution_requirement":"LOW",
    })
    r=build(c)
    assert r.scarcity_context is None
    assert "CERTIFIED_SCARCITY_CONTEXT_NOT_AVAILABLE" in r.unknowns


@pytest.mark.parametrize("value",[-1,True,"three",None])
def test_invalid_numeric_assumption_rejected(value):
    c=context(assumptions={
        "candidate_buyer_depth":value,"candidate_comparable_depth":8,
        "candidate_resale_competition":7,"candidate_substitution_requirement":"MODERATE",
    })
    with pytest.raises(ValueError,match="buyer_depth candidate"):
        build(c)


def test_scenario_identity_mismatch_rejected():
    c=context();e=evidence(c)
    with pytest.raises(ValueError,match="scenario identity mismatch"):
        build(c,e,dstate(c,e,scenario_id="OTHER"))


def test_evidence_context_lineage_mismatch_rejected():
    c=context();e=evidence(c,context_fp="9"*64)
    with pytest.raises(ValueError,match="context/evidence lineage mismatch"):
        build(c,e,dstate(c,e,context_fp="9"*64))


def test_pricing_timing_context_lineage_mismatch_rejected():
    c=context();e=evidence(c)
    with pytest.raises(ValueError,match="context/pricing timing lineage mismatch"):
        build(c,e,dstate(c,e,context_fp="9"*64))


def test_pricing_timing_evidence_lineage_mismatch_rejected():
    c=context();e=evidence(c)
    with pytest.raises(ValueError,match="evidence/pricing timing lineage mismatch"):
        build(c,e,dstate(c,e,evidence_fp="9"*64))


def test_unknowns_limitations_and_patterns_are_carried_forward():
    c=context(patterns=(pattern("APPLICABLE","P1"),pattern("UNKNOWN","P2")))
    r=build(c)
    assert r.applicable_pattern_ids==("P1",) and r.unknown_pattern_ids==("P2",)
    assert "historical sample thin" in r.unknowns
    assert any("not buyer-behavior predictions or recommendations" in x for x in r.limitations)


def test_state_is_deterministic_and_replayable():
    c=context();e=evidence(c);d=dstate(c,e)
    a=build(c,e,d);b=build(c,e,d)
    assert a==b
    assert validate_buyer_substitution_state_replay(a,context=c,evidence_set=e,pricing_timing_state=d,registry=registry())


def test_no_prediction_recommendation_ranking_or_execution_fields_exist():
    forbidden={
        "prediction","predicted_demand","sale_probability","recommended_action",
        "recommended_substitution","rank","winner","utility_score","seller_score",
        "execute","execution_state","causal_effect",
    }
    for cls in (NumericDimensionPosition,CategoricalDimensionPosition,BuyerSubstitutionCompetitiveState):
        assert {x.name for x in fields(cls)}.isdisjoint(forbidden)
