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
from src.seller_intelligence.timeline import (
    GovernedTimelineSnapshot,
    build_seller_decision_timeline,
    load_seller_timeline_registry,
)

O_REG="registries/seller_intelligence/m11-001-seller-opportunity-v1.0.yaml"
S_REG="registries/seller_intelligence/m11-002-property-seller-strategy-v1.0.yaml"
SC_REG="registries/seller_intelligence/m11-003-seller-scenario-sensitivity-v1.0.yaml"
T_REG="registries/seller_intelligence/m11-004-seller-decision-timeline-v1.0.yaml"
M11_001_FP="a"*64
M11_002_FP="b"*64
M11_003_FP="c"*64


def make_strategy(*, pressure="HIGH", buyer_depth="THIN", week="WORSENING", stale_depth=False, missing_week=False):
    alternatives=[]
    count=5 if pressure=="HIGH" else (2 if pressure=="MODERATE" else 0)
    builders=2 if pressure=="HIGH" else (1 if pressure=="MODERATE" else 0)
    idx=1
    for _ in range(count):
        alternatives.append(GovernedAlternativeInput(
            alternative_id=f"A-{idx}",subject_property_id="SUBJECT-1",
            alternative_property_id=f"P-{idx}",alternative_type="CLOSE_SUBSTITUTE",
            baseline_certified=True,qa_status="PASS",output_tier="SELLER",
            freshness_state="CURRENT",evidence_fingerprint=f"{idx:064x}",
        )); idx+=1
    for _ in range(builders):
        alternatives.append(GovernedAlternativeInput(
            alternative_id=f"A-{idx}",subject_property_id="SUBJECT-1",
            alternative_property_id=f"P-{idx}",alternative_type="BUILDER_ALTERNATIVE",
            baseline_certified=True,qa_status="PASS",output_tier="SELLER",
            freshness_state="CURRENT",evidence_fingerprint=f"{idx:064x}",
        )); idx+=1
    opp=build_seller_opportunity(
        subject_property_id="SUBJECT-1",alternatives=alternatives,
        registry=load_seller_opportunity_registry(O_REG),
    )
    rows=[
        ("BUYER_DEPTH",buyer_depth,"STALE" if stale_depth else "CURRENT"),
        ("VERIFIED_DIFFERENTIATION","LIMITED","CURRENT"),
        ("NEW_CONSTRUCTION_PRESSURE",pressure,"CURRENT"),
        ("PRICING_RESPONSE_ENVIRONMENT","WEAK","CURRENT"),
    ]
    if not missing_week:
        rows.append(("WEEK_OVER_WEEK_DIRECTION",week,"CURRENT"))
    findings=[
        GovernedStrategyFinding(
            finding_id=f"F-{i}",subject_property_id="SUBJECT-1",dimension=d,state=s,
            summary=f"Governed {d} summary",baseline_certified=True,qa_status="PASS",
            output_tier="SELLER",freshness_state=fresh,evidence_fingerprint=f"{100+i:064x}",
        )
        for i,(d,s,fresh) in enumerate(rows,1)
    ]
    return build_property_seller_strategy(
        opportunity=opp,m11_001_certified=True,m11_001_evidence_fingerprint=M11_001_FP,
        findings=findings,registry=load_seller_strategy_registry(S_REG),
    )


def scenario(strategy):
    return evaluate_seller_scenario(
        scenario_id="SC-1",strategy=strategy,m11_002_certified=True,
        m11_002_evidence_fingerprint=M11_002_FP,
        assumptions=[ScenarioAssumption(
            assumption_id="H-1",subject_property_id="SUBJECT-1",
            target="BUYER_DEPTH",hypothetical_state="DEEP",
            rationale="What-if buyer depth improves",hypothetical=True,
        )],
        registry=load_seller_scenario_registry(SC_REG),
    )


def snap(i,ts,strategy,with_scenario=False,certified=True):
    sc=scenario(strategy) if with_scenario else None
    return GovernedTimelineSnapshot(
        snapshot_id=f"S-{i}",observed_at=ts,strategy=strategy,
        strategy_certified=certified,strategy_evidence_fingerprint=f"{200+i:064x}",
        scenario=sc,scenario_certified=with_scenario,
        scenario_evidence_fingerprint=M11_003_FP if with_scenario else None,
    )


def registry():
    return load_seller_timeline_registry(T_REG)


def build(rows):
    return build_seller_decision_timeline(snapshots=rows,registry=registry())


def test_single_snapshot_creates_current_timeline_without_review_event():
    s=make_strategy()
    result=build([snap(1,"2026-09-01T09:00:00-07:00",s)])
    assert result.current_snapshot_id=="S-1"
    assert result.superseded_snapshot_ids==()
    assert result.entries[0].monitoring_event is None


def test_timeline_orders_snapshots_chronologically_and_is_deterministic():
    a=make_strategy(pressure="LOW",buyer_depth="DEEP",week="STABLE")
    b=make_strategy()
    rows=[
        snap(2,"2026-09-08T09:00:00-07:00",b),
        snap(1,"2026-09-01T09:00:00-07:00",a),
    ]
    x=build(rows)
    y=build(list(reversed(rows)))
    assert [e.snapshot_id for e in x.entries]==["S-1","S-2"]
    assert x.timeline_fingerprint==y.timeline_fingerprint


def test_prior_snapshot_is_explicitly_superseded():
    a=make_strategy(pressure="LOW",buyer_depth="DEEP",week="STABLE")
    b=make_strategy()
    result=build([
        snap(1,"2026-09-01T09:00:00-07:00",a),
        snap(2,"2026-09-08T09:00:00-07:00",b),
    ])
    assert result.superseded_snapshot_ids==("S-1",)
    assert result.entries[1].prior_snapshot_id=="S-1"
    assert result.entries[1].prior_snapshot_superseded is True


def test_meaningful_strategy_changes_emit_human_review_event():
    a=make_strategy(pressure="LOW",buyer_depth="DEEP",week="STABLE")
    b=make_strategy()
    result=build([
        snap(1,"2026-09-01T09:00:00-07:00",a),
        snap(2,"2026-09-08T09:00:00-07:00",b),
    ])
    event=result.entries[1].monitoring_event
    assert event is not None
    assert event.event_type=="HUMAN_REVIEW_REQUIRED"
    assert event.human_review_required is True
    assert "COMPETITIVE_PRESSURE:CHANGED" in event.reasons
    assert "BUYER_DEPTH:CHANGED" in event.reasons
    assert event.external_action_capability=="NONE"
    assert event.public_eligible is False


def test_stale_or_ineligible_evidence_becomes_explicitly_suppressed():
    a=make_strategy(buyer_depth="DEEP")
    b=make_strategy(buyer_depth="THIN",stale_depth=True)
    result=build([
        snap(1,"2026-09-01T09:00:00-07:00",a),
        snap(2,"2026-09-08T09:00:00-07:00",b),
    ])
    changes={c.target:c for c in result.entries[1].changes}
    assert changes["BUYER_DEPTH"].current_status=="SUPPRESSED"
    assert changes["BUYER_DEPTH"].transition=="BECAME_SUPPRESSED"
    assert "BUYER_DEPTH:BECAME_SUPPRESSED" in result.entries[1].monitoring_event.reasons


def test_missing_evidence_transition_is_explicit():
    a=make_strategy(week="STABLE")
    b=make_strategy(missing_week=True)
    result=build([
        snap(1,"2026-09-01T09:00:00-07:00",a),
        snap(2,"2026-09-08T09:00:00-07:00",b),
    ])
    changes={c.target:c for c in result.entries[1].changes}
    assert changes["WEEK_OVER_WEEK_DIRECTION"].transition=="BECAME_MISSING"


def test_newly_current_evidence_transition_is_explicit():
    a=make_strategy(missing_week=True)
    b=make_strategy(week="IMPROVING")
    result=build([
        snap(1,"2026-09-01T09:00:00-07:00",a),
        snap(2,"2026-09-08T09:00:00-07:00",b),
    ])
    changes={c.target:c for c in result.entries[1].changes}
    assert changes["WEEK_OVER_WEEK_DIRECTION"].transition=="NEWLY_CURRENT"


def test_review_trigger_newly_triggered_or_cleared_is_visible_as_change():
    a=make_strategy(pressure="LOW",buyer_depth="DEEP",week="STABLE")
    b=make_strategy()
    result=build([
        snap(1,"2026-09-01T09:00:00-07:00",a),
        snap(2,"2026-09-08T09:00:00-07:00",b),
    ])
    changes={c.target:c for c in result.entries[1].changes}
    assert changes["REVIEW_DAY_7"].prior_state=="NOT_TRIGGERED"
    assert changes["REVIEW_DAY_7"].current_state=="TRIGGERED"
    assert changes["REVIEW_DAY_7"].transition=="CHANGED"


def test_scenario_hypothetical_lineage_remains_separate_from_strategy_facts():
    s=make_strategy()
    result=build([snap(1,"2026-09-01T09:00:00-07:00",s,with_scenario=True)])
    e=result.entries[0]
    assert e.strategy_lineage_fingerprints
    assert e.hypothetical_lineage_fingerprints
    assert set(e.strategy_lineage_fingerprints).isdisjoint(e.hypothetical_lineage_fingerprints)


def test_monitoring_instruction_is_non_prescriptive_and_non_actionable():
    a=make_strategy(pressure="LOW",buyer_depth="DEEP",week="STABLE")
    b=make_strategy()
    result=build([
        snap(1,"2026-09-01T09:00:00-07:00",a),
        snap(2,"2026-09-08T09:00:00-07:00",b),
    ])
    text=result.entries[1].monitoring_event.instruction.lower()
    assert "does not recommend or execute a price change" in text
    assert "alter strategy" in text
    assert "publish information" in text
    assert "authorize an external action" in text


def test_uncertified_snapshot_fails_closed():
    with pytest.raises(ValueError,match="certified M11-002 strategy snapshot required"):
        build([snap(1,"2026-09-01T09:00:00-07:00",make_strategy(),certified=False)])


def test_duplicate_timestamp_fails_closed():
    with pytest.raises(ValueError,match="timestamps must be unique"):
        build([
            snap(1,"2026-09-01T09:00:00-07:00",make_strategy()),
            snap(2,"2026-09-01T09:00:00-07:00",make_strategy()),
        ])


def test_naive_timestamp_fails_closed():
    with pytest.raises(ValueError,match="must include timezone"):
        build([snap(1,"2026-09-01T09:00:00",make_strategy())])


def test_output_remains_seller_only_nonpublic_no_action():
    result=build([snap(1,"2026-09-01T09:00:00-07:00",make_strategy())])
    assert result.output_tier=="SELLER"
    assert result.public_eligible is False
    assert result.external_action_capability=="NONE"


def test_prohibited_fields_do_not_exist():
    names={x.name for x in fields(type(build([snap(1,"2026-09-01T09:00:00-07:00",make_strategy())])))}
    assert names.isdisjoint(set(registry()["prohibited_output_fields"]))
