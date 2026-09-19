from dataclasses import fields, replace

import pytest

from src.community_temporal_state.scenario_baseline import CertifiedScenarioBaseline
from src.community_temporal_state.scenario_buyer_depth_substitution import (
    BuyerDepthSubstitutionCompetitiveState,
    DescriptiveScenarioPosition,
    HistoricalNumericSummary,
    build_buyer_depth_substitution_state,
    load_buyer_depth_substitution_registry,
    validate_buyer_depth_substitution_replay,
)
from src.community_temporal_state.scenario_evidence import ScenarioEvidenceRecord, ScenarioEvidenceSet
from src.community_temporal_state.scenario_pricing_timing import (
    build_pricing_timing_scenario_state,
    load_pricing_timing_registry,
)

REGISTRY="registries/community_temporal_state/m13-006e-buyer-depth-substitution-v1.0.yaml"
D_REGISTRY="registries/community_temporal_state/m13-006d-pricing-timing-v1.0.yaml"


def registry():
    return load_buyer_depth_substitution_registry(REGISTRY)


def record(entry_id, fact_key, value, valid_from):
    return ScenarioEvidenceRecord(
        entry_id=entry_id,
        entry_fingerprint=(entry_id[-1].lower() if entry_id[-1].lower() in "abcdef" else "1")*64,
        state="INCLUDED",
        reason_codes=("GOVERNED_QUERY_MATCH",),
        scope="COMMUNITY",
        scope_id="SAN-TAN-HEIGHTS",
        fact_key=fact_key,
        fact_value=value,
        valid_from=valid_from,
        valid_to=None,
        known_at=valid_from,
        truth_state="ASSERTED",
        source_fingerprints=("7"*64,),
        evidence_fingerprints=("8"*64,),
        previous_entry_fingerprint=None,
        limitations=("Historical observation only.",),
        record_fingerprint="9"*64,
    )


def context(*,facts=None,assumptions=None,fp="a"*64):
    return CertifiedScenarioBaseline(
        scenario_id="SCENARIO-1",
        scenario_contract_fingerprint="b"*64,
        community_id="SAN-TAN-HEIGHTS",
        subject_id="PROPERTY-1",
        baseline_snapshot_id="SNAPSHOT-1",
        baseline_fingerprint="c"*64,
        facts=tuple(sorted((facts or {
            "current_list_price":500000,
            "current_listing_date":"2026-09-01",
            "buyer_depth":4,
            "substitution_requirement":"MODERATE",
            "competitive_set_size":6,
        }).items())),
        fact_source_fingerprints=("d"*64,),
        assumptions=tuple(sorted((assumptions or {
            "candidate_list_price":525000,
            "candidate_listing_date":"2026-09-15",
            "candidate_buyer_depth":5,
            "candidate_substitution_requirement":"HIGH",
            "candidate_competitive_set_size":8,
        }).items())),
        pattern_applicability=(),
        unknowns=("pool status unknown",),
        limitations=("Certified point-in-time context.",),
        context_fingerprint=fp,
    )


def evidence(ctx=None,*,scenario_id="SCENARIO-1",context_fp=None,evidence_fp="6"*64):
    c=ctx or context()
    rows=(
        record("E1","buyer_depth",2,"2026-01-01T00:00:00+00:00"),
        record("E2","buyer_depth",4,"2026-02-01T00:00:00+00:00"),
        record("E3","buyer_depth",6,"2026-03-01T00:00:00+00:00"),
        record("E4","substitution_depth",1,"2026-01-01T00:00:00+00:00"),
        record("E5","substitution_depth",3,"2026-02-01T00:00:00+00:00"),
        record("E6","competitive_set_size",5,"2026-01-01T00:00:00+00:00"),
        record("E7","competitive_set_size",9,"2026-03-01T00:00:00+00:00"),
    )
    return ScenarioEvidenceSet(
        evidence_set_id="ESET-1",
        scenario_id=scenario_id,
        scenario_context_fingerprint=context_fp or c.context_fingerprint,
        temporal_ledger_fingerprint="e"*64,
        query_fingerprint="f"*64,
        included=rows,
        excluded=(),
        source_fingerprints=("7"*64,),
        evidence_fingerprints=("8"*64,),
        unknowns=("historical coverage limitation",),
        limitations=("Historical evidence is descriptive.",),
        evidence_set_fingerprint=evidence_fp,
    )


def d_state(c=None,e=None):
    ctx=c or context()
    ev=e or evidence(ctx)
    return build_pricing_timing_scenario_state(
        context=ctx,
        evidence_set=ev,
        registry=load_pricing_timing_registry(D_REGISTRY),
    )


def build(c=None,e=None,d=None):
    ctx=c or context()
    ev=e or evidence(ctx)
    ds=d or d_state(ctx,ev)
    return build_buyer_depth_substitution_state(
        context=ctx,
        evidence_set=ev,
        pricing_timing_state=ds,
        registry=registry(),
    )


def test_registry_is_frozen_and_hard_policies_enabled():
    r=registry()
    assert r["status"]=="FROZEN"
    assert r["ticket"]=="M13-006E"
    for key in (
        "no_demand_prediction","no_probability_prediction","no_absorption_prediction",
        "no_recommendation","no_competitor_ranking","no_scenario_ranking",
        "no_causal_inference","no_execution",
    ):
        assert r["policy"][key] is True


def test_buyer_depth_position_is_descriptive_difference_only():
    p=build().buyer_depth_position
    assert p is not None
    assert p.candidate_value==5.0
    assert p.reference_value==4.0
    assert p.absolute_difference==1.0
    assert p.percent_difference==25.0
    assert p.relation=="ABOVE_REFERENCE"


def test_competitive_set_position_is_descriptive_difference_only():
    p=build().competitive_set_position
    assert p.candidate_value==8.0
    assert p.reference_value==6.0
    assert p.absolute_difference==2.0
    assert round(p.percent_difference,6)==33.333333


def test_categorical_substitution_is_same_or_different_only():
    p=build().substitution_position
    assert p is not None
    assert p.candidate_value=="HIGH"
    assert p.reference_value=="MODERATE"
    assert p.relation=="DIFFERENT"
    assert p.absolute_difference is None
    assert p.percent_difference is None


def test_same_categorical_substitution_is_same():
    c=context(assumptions={
        "candidate_list_price":525000,
        "candidate_listing_date":"2026-09-15",
        "candidate_buyer_depth":5,
        "candidate_substitution_requirement":"MODERATE",
        "candidate_competitive_set_size":8,
    })
    assert build(c).substitution_position.relation=="SAME"


def test_missing_explicit_buyer_depth_assumption_is_unknown_not_default():
    c=context(assumptions={
        "candidate_list_price":525000,
        "candidate_listing_date":"2026-09-15",
        "candidate_substitution_requirement":"HIGH",
        "candidate_competitive_set_size":8,
    })
    s=build(c)
    assert s.buyer_depth_position is None
    assert "EXPLICIT_BUYER_DEPTH_ASSUMPTION_NOT_PROVIDED" in s.unknowns


def test_missing_certified_competitive_reference_is_unknown():
    c=context(
        facts={
            "current_list_price":500000,
            "current_listing_date":"2026-09-01",
            "buyer_depth":4,
            "substitution_requirement":"MODERATE",
        }
    )
    s=build(c)
    assert s.competitive_set_position is None
    assert "CERTIFIED_COMPETITIVE_SET_SIZE_REFERENCE_NOT_AVAILABLE" in s.unknowns


def test_numeric_and_categorical_type_mismatch_is_rejected():
    c=context(assumptions={
        "candidate_list_price":525000,
        "candidate_listing_date":"2026-09-15",
        "candidate_buyer_depth":"HIGH",
        "candidate_substitution_requirement":"HIGH",
        "candidate_competitive_set_size":8,
    })
    with pytest.raises(ValueError,match="types must both"):
        build(c)


def test_buyer_depth_history_is_descriptive_distribution():
    h=build().buyer_depth_history
    assert h.observation_count==3
    assert h.minimum==2.0
    assert h.maximum==6.0
    assert h.mean==4.0
    assert h.latest==6.0


def test_competitive_history_is_descriptive_distribution():
    h=build().competitive_set_history
    assert h.observation_count==2
    assert h.minimum==5.0
    assert h.maximum==9.0
    assert h.mean==7.0
    assert h.latest==9.0


def test_substitution_numeric_history_is_separate_from_categorical_scenario_position():
    s=build()
    assert s.substitution_position.candidate_value=="HIGH"
    assert s.substitution_history.observation_count==2
    assert s.substitution_history.mean==2.0


def test_no_numeric_history_yields_explicit_unknown():
    c=context()
    ev=replace(evidence(c),included=())
    # Evidence fingerprint is an upstream certified artifact id for this test fixture.
    s=build(c,ev,d_state(c,ev))
    assert s.buyer_depth_history.observation_count==0
    assert "NO_NUMERIC_BUYER_DEPTH_HISTORY_IN_GOVERNED_EVIDENCE" in s.unknowns
    assert "NO_NUMERIC_SUBSTITUTION_HISTORY_IN_GOVERNED_EVIDENCE" in s.unknowns
    assert "NO_NUMERIC_COMPETITIVE_SET_HISTORY_IN_GOVERNED_EVIDENCE" in s.unknowns


def test_scenario_identity_mismatch_is_rejected():
    c=context()
    ev=evidence(c,scenario_id="OTHER")
    with pytest.raises(ValueError,match="scenario identity mismatch"):
        build(c,ev,d_state(c,ev))


def test_context_evidence_lineage_mismatch_is_rejected():
    c=context()
    ev=evidence(c,context_fp="0"*64)
    # D cannot be built from mismatched C evidence, so use a valid D then prove E rejects C mismatch first.
    ds=d_state(c,evidence(c))
    with pytest.raises(ValueError,match="context/evidence lineage mismatch"):
        build(c,ev,ds)


def test_tampered_d_state_is_rejected():
    c=context(); ev=evidence(c); ds=d_state(c,ev)
    tampered=replace(ds,included_historical_evidence_count=999)
    with pytest.raises(ValueError,match="replay failed"):
        build(c,ev,tampered)


def test_d_context_lineage_mismatch_is_rejected():
    c=context(); ev=evidence(c); ds=d_state(c,ev)
    bad=replace(ds,scenario_context_fingerprint="0"*64)
    # Recompute is intentionally absent: a changed certified D artifact must fail replay.
    with pytest.raises(ValueError,match="replay failed"):
        build(c,ev,bad)


def test_limitations_and_evidence_lineage_are_preserved():
    s=build()
    assert s.evidence_source_fingerprints==("7"*64,)
    assert "historical coverage limitation" in s.unknowns
    assert any("do not forecast demand" in x for x in s.limitations)


def test_state_is_deterministic_and_replayable():
    c=context(); ev=evidence(c); ds=d_state(c,ev)
    a=build(c,ev,ds)
    b=build(c,ev,ds)
    assert a==b
    assert validate_buyer_depth_substitution_replay(
        a,context=c,evidence_set=ev,pricing_timing_state=ds,registry=registry()
    )


def test_no_prediction_recommendation_ranking_or_execution_fields_exist():
    forbidden={
        "predicted_buyer_depth","buyer_probability","absorption_probability",
        "sale_probability","recommended_substitution_strategy",
        "recommended_competitive_set","recommended_action","rank","winner",
        "utility_score","seller_score","execute","execution_state","causal_effect",
    }
    for cls in (
        DescriptiveScenarioPosition,
        HistoricalNumericSummary,
        BuyerDepthSubstitutionCompetitiveState,
    ):
        assert {x.name for x in fields(cls)}.isdisjoint(forbidden)
