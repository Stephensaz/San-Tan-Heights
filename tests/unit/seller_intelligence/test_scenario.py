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
from src.seller_intelligence.scenario import (
    ScenarioAssumption,
    evaluate_seller_scenario,
    load_seller_scenario_registry,
)

O_REG="registries/seller_intelligence/m11-001-seller-opportunity-v1.0.yaml"
S_REG="registries/seller_intelligence/m11-002-property-seller-strategy-v1.0.yaml"
SC_REG="registries/seller_intelligence/m11-003-seller-scenario-sensitivity-v1.0.yaml"
M11_001_FP="a"*64
M11_002_FP="b"*64


def strategy(*, missing_week=False):
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
    opp=build_seller_opportunity(
        subject_property_id="SUBJECT-1",
        alternatives=alternatives,
        registry=load_seller_opportunity_registry(O_REG),
    )
    rows=[
        ("BUYER_DEPTH","THIN"),
        ("VERIFIED_DIFFERENTIATION","LIMITED"),
        ("NEW_CONSTRUCTION_PRESSURE","HIGH"),
        ("PRICING_RESPONSE_ENVIRONMENT","WEAK"),
    ]
    if not missing_week:
        rows.append(("WEEK_OVER_WEEK_DIRECTION","WORSENING"))
    findings=[
        GovernedStrategyFinding(
            finding_id=f"F-{i}",
            subject_property_id="SUBJECT-1",
            dimension=dimension,
            state=state,
            summary=f"Governed {dimension} summary",
            baseline_certified=True,
            qa_status="PASS",
            output_tier="SELLER",
            freshness_state="CURRENT",
            evidence_fingerprint=f"{100+i:064x}",
        )
        for i,(dimension,state) in enumerate(rows,1)
    ]
    return build_property_seller_strategy(
        opportunity=opp,
        m11_001_certified=True,
        m11_001_evidence_fingerprint=M11_001_FP,
        findings=findings,
        registry=load_seller_strategy_registry(S_REG),
    )


def registry():
    return load_seller_scenario_registry(SC_REG)


def assumption(i,target,state,*,hypothetical=True):
    return ScenarioAssumption(
        assumption_id=f"H-{i}",
        subject_property_id="SUBJECT-1",
        target=target,
        hypothetical_state=state,
        rationale=f"What-if assumption for {target}",
        hypothetical=hypothetical,
    )


def evaluate(rows, *, certified=True, base=None):
    return evaluate_seller_scenario(
        scenario_id="SCENARIO-1",
        strategy=base or strategy(),
        m11_002_certified=certified,
        m11_002_evidence_fingerprint=M11_002_FP,
        assumptions=rows,
        registry=registry(),
    )


def test_scenario_is_deterministic_and_assumption_order_independent():
    rows=[
        assumption(1,"BUYER_DEPTH","DEEP"),
        assumption(2,"COMPETITIVE_PRESSURE","LOW"),
        assumption(3,"REVIEW_DAY_7","NOT_TRIGGERED"),
    ]
    a=evaluate(rows)
    b=evaluate(list(reversed(rows)))
    assert a.scenario_fingerprint==b.scenario_fingerprint
    assert [x.comparison_fingerprint for x in a.comparisons]==[x.comparison_fingerprint for x in b.comparisons]


def test_baseline_and_hypothetical_lineage_are_separate():
    result=evaluate([assumption(1,"BUYER_DEPTH","DEEP")])
    assert result.baseline_lineage_fingerprints
    assert result.hypothetical_assumption_fingerprints
    assert set(result.baseline_lineage_fingerprints).isdisjoint(result.hypothetical_assumption_fingerprints)
    assert result.baseline_strategy_fingerprint==strategy().strategy_fingerprint


def test_changed_dimension_compares_certified_baseline_to_hypothesis():
    result=evaluate([assumption(1,"BUYER_DEPTH","DEEP")])
    c=result.comparisons[0]
    assert c.target=="BUYER_DEPTH"
    assert c.baseline_status=="CURRENT"
    assert c.baseline_state=="THIN"
    assert c.hypothetical_state=="DEEP"
    assert c.change_type=="CHANGED"


def test_unchanged_assumption_is_explicit():
    result=evaluate([assumption(1,"NEW_CONSTRUCTION_PRESSURE","HIGH")])
    assert result.comparisons[0].change_type=="UNCHANGED"
    assert result.unchanged_targets==("NEW_CONSTRUCTION_PRESSURE",)


def test_missing_baseline_dimension_remains_hypothetical_only():
    result=evaluate(
        [assumption(1,"WEEK_OVER_WEEK_DIRECTION","IMPROVING")],
        base=strategy(missing_week=True),
    )
    c=result.comparisons[0]
    assert c.baseline_status=="MISSING"
    assert c.baseline_state is None
    assert c.change_type=="HYPOTHETICAL_ONLY"


def test_competitive_pressure_can_be_modeled_without_rewriting_baseline():
    base=strategy()
    result=evaluate([assumption(1,"COMPETITIVE_PRESSURE","LOW")],base=base)
    c=result.comparisons[0]
    assert c.baseline_state=="HIGH"
    assert c.hypothetical_state=="LOW"
    assert base.competitive_pressure_level=="HIGH"
    assert result.baseline_strategy_fingerprint==base.strategy_fingerprint


def test_review_trigger_state_can_be_scenario_modeled():
    result=evaluate([assumption(1,"REVIEW_DAY_10","NOT_TRIGGERED")])
    c=result.comparisons[0]
    assert c.baseline_state=="TRIGGERED"
    assert c.hypothetical_state=="NOT_TRIGGERED"
    assert c.change_type=="CHANGED"


def test_unmodeled_targets_are_explicit():
    result=evaluate([assumption(1,"BUYER_DEPTH","DEEP")])
    assert "COMPETITIVE_PRESSURE" in result.unmodeled_targets
    assert "REVIEW_DAY_14" in result.unmodeled_targets
    assert "BUYER_DEPTH" not in result.unmodeled_targets


def test_assumption_must_be_explicitly_hypothetical():
    with pytest.raises(ValueError,match="explicitly hypothetical"):
        evaluate([assumption(1,"BUYER_DEPTH","DEEP",hypothetical=False)])


def test_unsupported_target_fails_closed():
    with pytest.raises(ValueError,match="unsupported scenario target"):
        evaluate([assumption(1,"LIST_PRICE","500000")])


def test_unsupported_state_fails_closed():
    with pytest.raises(ValueError,match="unsupported hypothetical scenario state"):
        evaluate([assumption(1,"BUYER_DEPTH","CERTAIN_SALE")])


def test_duplicate_target_fails_closed():
    with pytest.raises(ValueError,match="duplicate scenario target"):
        evaluate([
            assumption(1,"BUYER_DEPTH","DEEP"),
            assumption(2,"BUYER_DEPTH","BALANCED"),
        ])


def test_uncertified_m11_002_parent_fails_closed():
    with pytest.raises(ValueError,match="certified M11-002 strategy required"):
        evaluate([assumption(1,"BUYER_DEPTH","DEEP")],certified=False)


def test_output_remains_hypothetical_seller_only_nonpublic_no_action():
    result=evaluate([assumption(1,"BUYER_DEPTH","DEEP")])
    assert result.hypothetical_only is True
    assert result.output_tier=="SELLER"
    assert result.public_eligible is False
    assert result.external_action_capability=="NONE"
    assert "hypothetical sensitivity scenario" in result.disclaimer
    assert "not a statement of current fact" in result.disclaimer


def test_disclaimer_prohibits_price_prediction_proceeds_behavior_and_actions():
    d=evaluate([]).disclaimer.lower()
    assert "recommend a list price" in d
    assert "predict a sale price" in d
    assert "guarantee proceeds or outcomes" in d
    assert "predict seller acceptance or buyer behavior" in d
    assert "authorize any external action" in d


def test_prohibited_output_fields_do_not_exist():
    names={x.name for x in fields(type(evaluate([])))}
    prohibited=set(registry()["prohibited_output_fields"])
    assert names.isdisjoint(prohibited)
