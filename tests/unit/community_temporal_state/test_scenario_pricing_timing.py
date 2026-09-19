from dataclasses import fields, replace

import pytest

from src.community_temporal_state.scenario_baseline import (
    CertifiedScenarioBaseline,
    PatternApplicability,
)
from src.community_temporal_state.scenario_evidence import ScenarioEvidenceSet
from src.community_temporal_state.scenario_pricing_timing import (
    ListingTiming,
    PricingPosition,
    PricingTimingScenarioState,
    build_pricing_timing_scenario_state,
    load_pricing_timing_registry,
    validate_pricing_timing_state_replay,
)

REGISTRY = "registries/community_temporal_state/m13-006d-pricing-timing-v1.0.yaml"


def registry():
    return load_pricing_timing_registry(REGISTRY)


def pattern(state="APPLICABLE", pattern_id="P1"):
    return PatternApplicability(
        pattern_id=pattern_id,
        pattern_fingerprint="1" * 64,
        pattern_domain="pricing",
        pattern_statement="Historical descriptive association.",
        state=state,
        reason_codes=("GOVERNED_RULE_SATISFIED",),
        matched_fact_keys=("phase",),
        matched_assumption_keys=("candidate_list_price",),
        source_ledger_fingerprint="2" * 64,
        limitations=("Historical association only.",),
        applicability_fingerprint="3" * 64,
    )


def context(
    *,
    facts=None,
    assumptions=None,
    patterns=None,
    fp="a" * 64,
):
    return CertifiedScenarioBaseline(
        scenario_id="SCENARIO-1",
        scenario_contract_fingerprint="b" * 64,
        community_id="SAN-TAN-HEIGHTS",
        subject_id="PROPERTY-1",
        baseline_snapshot_id="SNAPSHOT-1",
        baseline_fingerprint="c" * 64,
        facts=tuple(sorted((facts or {
            "current_list_price": 500000,
            "current_listing_date": "2026-09-01",
        }).items())),
        fact_source_fingerprints=("d" * 64,),
        assumptions=tuple(sorted((assumptions or {
            "candidate_list_price": 525000,
            "candidate_listing_date": "2026-09-15",
        }).items())),
        pattern_applicability=tuple(patterns or (pattern(),)),
        unknowns=("pool status unknown",),
        limitations=("Certified point-in-time context.",),
        context_fingerprint=fp,
    )


def evidence(ctx=None, *, scenario_id="SCENARIO-1", context_fp=None):
    c = ctx or context()
    return ScenarioEvidenceSet(
        evidence_set_id="ESET-1",
        scenario_id=scenario_id,
        scenario_context_fingerprint=context_fp or c.context_fingerprint,
        temporal_ledger_fingerprint="e" * 64,
        query_fingerprint="f" * 64,
        included=(),
        excluded=(),
        source_fingerprints=("4" * 64,),
        evidence_fingerprints=("5" * 64,),
        unknowns=("historical sample thin",),
        limitations=("Historical evidence is descriptive.",),
        evidence_set_fingerprint="6" * 64,
    )


def build(ctx=None, ev=None):
    c = ctx or context()
    return build_pricing_timing_scenario_state(
        context=c,
        evidence_set=ev or evidence(c),
        registry=registry(),
    )


def test_registry_is_frozen_and_prohibitions_enabled():
    r = registry()
    assert r["status"] == "FROZEN"
    assert r["ticket"] == "M13-006D"
    for key in (
        "no_selected_price", "no_recommended_price", "no_recommended_timing",
        "no_prediction", "no_causal_inference", "no_ranking", "no_execution",
    ):
        assert r["policy"][key] is True


def test_pricing_position_is_descriptive_difference_only():
    result = build()
    p = result.pricing_position
    assert p is not None
    assert p.candidate_price == 525000.0
    assert p.reference_price == 500000.0
    assert p.absolute_difference == 25000.0
    assert p.percent_difference == 5.0
    assert p.direction == "ABOVE_REFERENCE"


def test_pricing_below_reference_is_described_without_judgment():
    c = context(assumptions={
        "candidate_list_price": 475000,
        "candidate_listing_date": "2026-09-15",
    })
    p = build(c).pricing_position
    assert p.direction == "BELOW_REFERENCE"
    assert p.percent_difference == -5.0


def test_same_price_is_same_direction():
    c = context(assumptions={
        "candidate_list_price": 500000,
        "candidate_listing_date": "2026-09-15",
    })
    assert build(c).pricing_position.direction == "SAME"


def test_listing_timing_is_day_difference_only():
    t = build().listing_timing
    assert t is not None
    assert t.reference_date == "2026-09-01"
    assert t.candidate_listing_date == "2026-09-15"
    assert t.day_difference == 14
    assert t.direction == "LATER_THAN_REFERENCE"


def test_earlier_listing_date_is_described():
    c = context(assumptions={
        "candidate_list_price": 525000,
        "candidate_listing_date": "2026-08-25",
    })
    t = build(c).listing_timing
    assert t.day_difference == -7
    assert t.direction == "EARLIER_THAN_REFERENCE"


def test_missing_price_assumption_yields_unknown_not_default():
    c = context(assumptions={"candidate_listing_date": "2026-09-15"})
    r = build(c)
    assert r.pricing_position is None
    assert "EXPLICIT_CANDIDATE_PRICE_NOT_PROVIDED" in r.unknowns


def test_missing_timing_assumption_yields_unknown_not_default():
    c = context(assumptions={"candidate_list_price": 525000})
    r = build(c)
    assert r.listing_timing is None
    assert "EXPLICIT_CANDIDATE_LISTING_DATE_NOT_PROVIDED" in r.unknowns


def test_missing_reference_price_yields_unknown():
    c = context(
        facts={"current_listing_date": "2026-09-01"},
        assumptions={
            "candidate_list_price": 525000,
            "candidate_listing_date": "2026-09-15",
        },
    )
    r = build(c)
    assert r.pricing_position is None
    assert "CERTIFIED_REFERENCE_PRICE_NOT_AVAILABLE" in r.unknowns


def test_missing_reference_date_yields_unknown():
    c = context(
        facts={"current_list_price": 500000},
        assumptions={
            "candidate_list_price": 525000,
            "candidate_listing_date": "2026-09-15",
        },
    )
    r = build(c)
    assert r.listing_timing is None
    assert "CERTIFIED_REFERENCE_DATE_NOT_AVAILABLE" in r.unknowns


@pytest.mark.parametrize("candidate", [-1, True, "525000"])
def test_invalid_candidate_price_rejected(candidate):
    c = context(assumptions={
        "candidate_list_price": candidate,
        "candidate_listing_date": "2026-09-15",
    })
    with pytest.raises(ValueError, match="candidate price"):
        build(c)


def test_invalid_reference_price_rejected():
    c = context(
        facts={"current_list_price": 0, "current_listing_date": "2026-09-01"}
    )
    with pytest.raises(ValueError, match="reference price"):
        build(c)


def test_invalid_date_rejected():
    c = context(assumptions={
        "candidate_list_price": 525000,
        "candidate_listing_date": "09/15/2026",
    })
    with pytest.raises(ValueError, match="ISO date"):
        build(c)


def test_evidence_and_pattern_context_is_descriptive_and_preserved():
    c = context(patterns=(pattern("APPLICABLE", "P1"), pattern("UNKNOWN", "P2")))
    r = build(c)
    assert r.applicable_pattern_ids == ("P1",)
    assert r.unknown_pattern_ids == ("P2",)
    assert r.evidence_source_fingerprints == ("4" * 64,)
    assert "historical sample thin" in r.unknowns
    assert any("not recommendations or forecasts" in x for x in r.limitations)


def test_scenario_identity_mismatch_rejected():
    c = context()
    with pytest.raises(ValueError, match="scenario identity mismatch"):
        build(c, evidence(c, scenario_id="OTHER"))


def test_evidence_context_lineage_mismatch_rejected():
    c = context()
    with pytest.raises(ValueError, match="context/evidence lineage mismatch"):
        build(c, evidence(c, context_fp="9" * 64))


def test_state_is_deterministic_and_replayable():
    c = context()
    e = evidence(c)
    a = build(c, e)
    b = build(c, e)
    assert a == b
    assert validate_pricing_timing_state_replay(
        a, context=c, evidence_set=e, registry=registry()
    )


def test_no_recommendation_prediction_ranking_or_execution_fields_exist():
    forbidden = {
        "recommended_price", "recommended_timing", "selected_price",
        "predicted_sale_price", "sale_probability", "predicted_dom",
        "rank", "winner", "utility_score", "seller_score",
        "execute", "execution_state", "causal_effect",
    }
    for cls in (PricingPosition, ListingTiming, PricingTimingScenarioState):
        assert {x.name for x in fields(cls)}.isdisjoint(forbidden)
