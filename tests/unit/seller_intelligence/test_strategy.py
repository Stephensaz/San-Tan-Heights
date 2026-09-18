from dataclasses import fields

import pytest

from src.seller_intelligence.opportunity import (
    GovernedAlternativeInput,
    build_seller_opportunity,
    load_seller_opportunity_registry,
)
from src.seller_intelligence.strategy import (
    GovernedStrategyFinding,
    build_property_seller_strategy,
    load_seller_strategy_registry,
)

O_REG="registries/seller_intelligence/m11-001-seller-opportunity-v1.0.yaml"
S_REG="registries/seller_intelligence/m11-002-property-seller-strategy-v1.0.yaml"
M11_001_EVIDENCE_FP="a"*64


def opportunity():
    alternatives=[
        GovernedAlternativeInput(
            alternative_id=f"A-{i}",
            subject_property_id="SUBJECT-1",
            alternative_property_id=f"P-{i}",
            alternative_type="CLOSE_SUBSTITUTE" if i<=5 else "BUILDER_ALTERNATIVE",
            baseline_certified=True,
            qa_status="PASS",
            output_tier="SELLER",
            freshness_state="CURRENT",
            evidence_fingerprint=f"{i:064x}",
        )
        for i in range(1,8)
    ]
    return build_seller_opportunity(
        subject_property_id="SUBJECT-1",
        alternatives=alternatives,
        registry=load_seller_opportunity_registry(O_REG),
    )


def finding(i,dimension,state,*,freshness="CURRENT",tier="SELLER",qa="PASS",certified=True):
    return GovernedStrategyFinding(
        finding_id=f"F-{i}",
        subject_property_id="SUBJECT-1",
        dimension=dimension,
        state=state,
        summary=f"Governed {dimension} summary",
        baseline_certified=certified,
        qa_status=qa,
        output_tier=tier,
        freshness_state=freshness,
        evidence_fingerprint=f"{100+i:064x}",
    )


def registry():
    return load_seller_strategy_registry(S_REG)


def full_findings():
    return [
        finding(1,"BUYER_DEPTH","THIN"),
        finding(2,"VERIFIED_DIFFERENTIATION","LIMITED"),
        finding(3,"NEW_CONSTRUCTION_PRESSURE","HIGH"),
        finding(4,"PRICING_RESPONSE_ENVIRONMENT","WEAK"),
        finding(5,"WEEK_OVER_WEEK_DIRECTION","WORSENING"),
    ]


def build(rows=None, certified=True):
    return build_property_seller_strategy(
        opportunity=opportunity(),
        m11_001_certified=certified,
        m11_001_evidence_fingerprint=M11_001_EVIDENCE_FP,
        findings=full_findings() if rows is None else rows,
        registry=registry(),
    )


def test_strategy_synthesis_is_deterministic_and_order_independent():
    a=build()
    b=build(list(reversed(full_findings())))
    assert a.strategy_fingerprint==b.strategy_fingerprint
    assert [x.dimension_fingerprint for x in a.dimensions]==[x.dimension_fingerprint for x in b.dimensions]


def test_all_required_property_strategy_dimensions_are_present():
    result=build()
    assert [x.dimension for x in result.dimensions]==[
        "BUYER_DEPTH",
        "VERIFIED_DIFFERENTIATION",
        "NEW_CONSTRUCTION_PRESSURE",
        "PRICING_RESPONSE_ENVIRONMENT",
        "WEEK_OVER_WEEK_DIRECTION",
    ]
    assert all(x.status=="CURRENT" for x in result.dimensions)


def test_strategy_preserves_m11_001_alternatives_and_pressure_lineage():
    opp=opportunity()
    result=build()
    assert result.buyer_alternative_set_fingerprint==opp.alternative_set.alternative_set_fingerprint
    assert result.competitive_pressure_fingerprint==opp.competitive_pressure.signal_fingerprint
    assert opp.result_fingerprint in result.lineage_fingerprints
    assert M11_001_EVIDENCE_FP in result.lineage_fingerprints


def test_stale_dimension_is_explicitly_suppressed_not_inferred():
    rows=full_findings()
    rows[0]=finding(1,"BUYER_DEPTH","THIN",freshness="STALE")
    result=build(rows)
    d={x.dimension:x for x in result.dimensions}["BUYER_DEPTH"]
    assert d.status=="SUPPRESSED"
    assert d.state is None
    assert d.suppressed_finding_ids==("F-1",)
    assert "BUYER_DEPTH:SUPPRESSED" in result.limitations


def test_missing_dimension_is_explicit():
    result=build(full_findings()[:-1])
    d={x.dimension:x for x in result.dimensions}["WEEK_OVER_WEEK_DIRECTION"]
    assert d.status=="MISSING"
    assert d.state is None
    assert "WEEK_OVER_WEEK_DIRECTION:MISSING" in result.limitations


def test_uncertified_strategy_finding_fails_closed():
    rows=full_findings()
    rows[0]=finding(1,"BUYER_DEPTH","THIN",certified=False)
    with pytest.raises(ValueError,match="uncertified community baseline input prohibited"):
        build(rows)


def test_uncertified_m11_001_parent_fails_closed():
    with pytest.raises(ValueError,match="certified M11-001 opportunity result required"):
        build(certified=False)


def test_day_7_trigger_is_evidence_based_and_non_prescriptive():
    result=build()
    t={x.day:x for x in result.review_triggers}[7]
    assert t.triggered is True
    assert "HIGH_CURRENT_COMPETITIVE_PRESSURE" in t.reasons
    assert "THIN_BUYER_DEPTH" in t.reasons
    assert "MARKET_DIRECTION_WORSENING" in t.reasons
    assert "does not prescribe a price change" in t.instruction


def test_day_10_trigger_uses_governed_strategy_conditions():
    result=build()
    t={x.day:x for x in result.review_triggers}[10]
    assert t.triggered is True
    assert set(t.reasons)=={
        "HIGH_NEW_CONSTRUCTION_PRESSURE",
        "LIMITED_VERIFIED_DIFFERENTIATION",
        "WEAK_PRICING_RESPONSE_ENVIRONMENT",
    }


def test_day_14_is_always_a_review_checkpoint_not_an_action():
    result=build([])
    t={x.day:x for x in result.review_triggers}[14]
    assert t.triggered is True
    assert t.reasons==("GOVERNED_DAY_14_STRATEGY_CHECKPOINT",)
    assert "authorize an external action" in t.instruction


def test_output_remains_seller_only_nonpublic_and_no_action():
    result=build()
    assert result.output_tier=="SELLER"
    assert result.public_eligible is False
    assert result.external_action_capability=="NONE"


def test_prohibited_price_value_motivation_and_outcome_fields_do_not_exist():
    names={x.name for x in fields(type(build()))}
    prohibited=set(registry()["prohibited_output_fields"])
    assert names.isdisjoint(prohibited)


def test_multiple_current_findings_for_same_dimension_fail_closed():
    rows=full_findings()+[finding(6,"BUYER_DEPTH","BALANCED")]
    with pytest.raises(ValueError,match="multiple current governed findings"):
        build(rows)


def test_non_seller_and_qa_failed_findings_are_suppressed():
    rows=[
        finding(1,"BUYER_DEPTH","THIN",tier="AGENT"),
        finding(2,"VERIFIED_DIFFERENTIATION","LIMITED",qa="FAIL"),
    ]
    result=build(rows)
    dims={x.dimension:x for x in result.dimensions}
    assert dims["BUYER_DEPTH"].status=="SUPPRESSED"
    assert dims["VERIFIED_DIFFERENTIATION"].status=="SUPPRESSED"
