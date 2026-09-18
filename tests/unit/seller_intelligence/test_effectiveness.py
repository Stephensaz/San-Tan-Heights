import pytest

from src.seller_intelligence.opportunity import GovernedAlternativeInput, build_seller_opportunity, load_seller_opportunity_registry
from src.seller_intelligence.strategy import GovernedStrategyFinding, build_property_seller_strategy, load_seller_strategy_registry
from src.seller_intelligence.scenario import ScenarioAssumption, evaluate_seller_scenario, load_seller_scenario_registry
from src.seller_intelligence.timeline import GovernedTimelineSnapshot, build_seller_decision_timeline, load_seller_timeline_registry
from src.seller_intelligence.communication import translate_seller_intelligence, load_communication_registry
from src.seller_intelligence.workspace import build_seller_intelligence_case, load_workspace_registry, make_human_decision
from src.seller_intelligence.effectiveness import make_observed_outcome, evaluate_effectiveness, load_effectiveness_registry

O="registries/seller_intelligence/m11-001-seller-opportunity-v1.0.yaml"
S="registries/seller_intelligence/m11-002-property-seller-strategy-v1.0.yaml"
SC="registries/seller_intelligence/m11-003-seller-scenario-sensitivity-v1.0.yaml"
T="registries/seller_intelligence/m11-004-seller-decision-timeline-v1.0.yaml"
C="registries/seller_intelligence/m11-005-communication-translation-v1.0.yaml"
W="registries/seller_intelligence/m11-006-seller-workspace-v1.0.yaml"
E="registries/seller_intelligence/m11-007-effectiveness-learning-v1.0.yaml"
FP1="a"*64; FP2="b"*64; FP3="c"*64; FP4="d"*64; FP5="e"*64; FP6="f"*64


def case_bundle(with_decision=True):
    opp=build_seller_opportunity(
        subject_property_id="SUBJECT-1",
        alternatives=[
            GovernedAlternativeInput("A-1","SUBJECT-1","P-1","CLOSE_SUBSTITUTE",True,"PASS","SELLER","CURRENT","1"*64),
            GovernedAlternativeInput("A-2","SUBJECT-1","P-2","BUILDER_ALTERNATIVE",True,"PASS","SELLER","CURRENT","2"*64),
        ],
        registry=load_seller_opportunity_registry(O),
    )
    prior=build_property_seller_strategy(
        opportunity=build_seller_opportunity(subject_property_id="SUBJECT-1",alternatives=[],registry=load_seller_opportunity_registry(O)),
        m11_001_certified=True,m11_001_evidence_fingerprint=FP1,
        findings=[GovernedStrategyFinding("P-1","SUBJECT-1","BUYER_DEPTH","DEEP","Prior",True,"PASS","SELLER","CURRENT","3"*64)],
        registry=load_seller_strategy_registry(S),
    )
    strat=build_property_seller_strategy(
        opportunity=opp,m11_001_certified=True,m11_001_evidence_fingerprint=FP1,
        findings=[GovernedStrategyFinding("F-1","SUBJECT-1","BUYER_DEPTH","THIN","Current",True,"PASS","SELLER","CURRENT","4"*64)],
        registry=load_seller_strategy_registry(S),
    )
    scen=evaluate_seller_scenario(
        scenario_id="SC-1",strategy=strat,m11_002_certified=True,m11_002_evidence_fingerprint=FP2,
        assumptions=[ScenarioAssumption("H-1","SUBJECT-1","BUYER_DEPTH","DEEP","What if",True)],
        registry=load_seller_scenario_registry(SC),
    )
    timeline=build_seller_decision_timeline(
        snapshots=[
            GovernedTimelineSnapshot("S-1","2026-09-01T09:00:00-07:00",prior,True,"5"*64),
            GovernedTimelineSnapshot("S-2","2026-09-08T09:00:00-07:00",strat,True,"6"*64,scen,True,FP3),
        ],
        registry=load_seller_timeline_registry(T),
    )
    comm=translate_seller_intelligence(
        audience="SELLER",opportunity=opp,strategy=strat,scenario=scen,timeline=timeline,
        m11_001_certified=True,m11_002_certified=True,m11_003_certified=True,m11_004_certified=True,
        m11_001_evidence_fingerprint=FP1,m11_002_evidence_fingerprint=FP2,m11_003_evidence_fingerprint=FP3,
        m11_004_evidence_fingerprint=FP4,registry=load_communication_registry(C),
    )
    decisions=[]
    if with_decision:
        item_id="REVIEW-S-2-REVIEW"
        decisions=[make_human_decision(
            decision_id="D-1",review_item_id=item_id,decision_type="ACKNOWLEDGE_REVIEW",
            actor_id="USER-1",decided_at="2026-09-08T10:00:00-07:00",rationale="Reviewed",registry=load_workspace_registry(W),
        )]
    built=build_seller_intelligence_case(
        case_id="CASE-1",opportunity=opp,strategy=strat,scenario=scen,timeline=timeline,communication=comm,
        m11_001_certified=True,m11_002_certified=True,m11_003_certified=True,m11_004_certified=True,m11_005_certified=True,
        m11_001_evidence_fingerprint=FP1,m11_002_evidence_fingerprint=FP2,m11_003_evidence_fingerprint=FP3,
        m11_004_evidence_fingerprint=FP4,m11_005_evidence_fingerprint=FP5,
        human_decisions=decisions,registry=load_workspace_registry(W),
    )
    return built,timeline


def case(with_decision=True):
    return case_bundle(with_decision)[0]


def reg(): return load_effectiveness_registry(E)


def outcome(i,state="IMPROVED",kind="MARKET_RESPONSE",ts="2026-09-15T09:00:00-07:00"):
    return make_observed_outcome(
        outcome_id=f"O-{i}",subject_property_id="SUBJECT-1",outcome_type=kind,outcome_state=state,
        observed_at=ts,source_fingerprint=f"{100+i:064x}",notes="Observed downstream state",registry=reg(),
    )


def evaluate(rows, *, c=None, certified=True, timeline=None):
    if c is None:
        c,timeline=case_bundle()
    elif timeline is None:
        _,timeline=case_bundle()
    return evaluate_effectiveness(
        case=c,timeline=timeline,
        m11_004_certified=True,m11_004_evidence_fingerprint=FP4,
        m11_006_certified=certified,m11_006_evidence_fingerprint=FP6,
        outcomes=rows,registry=reg(),
    )


def test_effectiveness_is_deterministic_and_order_independent():
    a=evaluate([outcome(1),outcome(2,"STABLE")])
    b=evaluate([outcome(2,"STABLE"),outcome(1)])
    assert a.learning_fingerprint==b.learning_fingerprint


def test_observed_outcomes_are_preserved_as_immutable_records():
    o=outcome(1)
    result=evaluate([o])
    assert result.observed_outcomes==(o,)
    assert result.observed_outcomes[0].outcome_fingerprint==o.outcome_fingerprint


def test_review_association_is_explicitly_noncausal():
    result=evaluate([outcome(1)])
    a=[x for x in result.associations if x.association_type=="PRECEDED_BY_REVIEW_EVENT"][0]
    assert a.causal_claim is False
    assert "association, not evidence of causation" in a.statement


def test_human_decision_association_is_explicitly_noncausal():
    result=evaluate([outcome(1)])
    a=[x for x in result.associations if x.association_type=="PRECEDED_BY_HUMAN_DECISION"][0]
    assert a.causal_claim is False
    assert "not evidence that the decision caused the outcome" in a.statement


def test_no_prior_human_decision_is_explicit():
    result=evaluate([outcome(1)],c=case(with_decision=False))
    assert any(x.association_type=="NO_PRIOR_HUMAN_DECISION" for x in result.associations)


def test_unknown_outcomes_remain_explicit():
    result=evaluate([outcome(1,"UNKNOWN")])
    assert result.unknown_outcome_ids==("O-1",)


def test_market_response_after_review_creates_advisory_calibration_candidate():
    result=evaluate([outcome(1,"WORSENED")])
    assert result.calibration_candidates
    c=result.calibration_candidates[0]
    assert c.candidate_type=="REVIEW_CONDITION_CALIBRATION"
    assert c.advisory_only is True
    assert c.promotion_status=="NOT_PROMOTED"
    assert "do not treat this as causal proof" in c.rationale


def test_unknown_market_response_creates_coverage_gap_candidate():
    result=evaluate([outcome(1,"UNKNOWN")])
    assert any(x.candidate_type=="OUTCOME_COVERAGE_GAP" for x in result.calibration_candidates)


def test_stable_market_response_does_not_create_review_calibration_candidate():
    result=evaluate([outcome(1,"STABLE")])
    assert not any(x.candidate_type=="REVIEW_CONDITION_CALIBRATION" for x in result.calibration_candidates)


def test_duplicate_outcome_id_fails_closed():
    o=outcome(1)
    with pytest.raises(ValueError,match="duplicate observed outcome_id"):
        evaluate([o,o])


def test_outcome_property_mismatch_fails_closed():
    bad=make_observed_outcome(
        outcome_id="O-X",subject_property_id="OTHER",outcome_type="MARKET_RESPONSE",outcome_state="STABLE",
        observed_at="2026-09-15T09:00:00-07:00",source_fingerprint="9"*64,notes="",registry=reg(),
    )
    with pytest.raises(ValueError,match="property mismatch"):
        evaluate([bad])


def test_uncertified_case_fails_closed():
    with pytest.raises(ValueError,match="certified M11-006 case required"):
        evaluate([outcome(1)],certified=False)


def test_naive_outcome_timestamp_rejected():
    with pytest.raises(ValueError,match="must include timezone"):
        outcome(1,ts="2026-09-15T09:00:00")


def test_unsupported_outcome_state_rejected():
    with pytest.raises(ValueError,match="unsupported observed outcome state"):
        outcome(1,state="CERTAIN_SALE")


def test_learning_output_is_internal_nonpublic_no_action():
    result=evaluate([outcome(1)])
    assert result.output_tier=="INTERNAL"
    assert result.public_eligible is False
    assert result.external_action_capability=="NONE"


def test_review_event_after_outcome_is_not_treated_as_preceding():
    c,timeline=case_bundle()
    early=outcome(9,ts="2026-09-05T09:00:00-07:00")
    result=evaluate([early],c=c,timeline=timeline)
    assert any(x.association_type=="NO_PRIOR_REVIEW_EVENT" for x in result.associations)
    assert not any(x.association_type=="PRECEDED_BY_REVIEW_EVENT" for x in result.associations)


def test_uncertified_timeline_fails_closed():
    c,timeline=case_bundle()
    with pytest.raises(ValueError,match="certified M11-004 timeline required"):
        evaluate_effectiveness(
            case=c,timeline=timeline,
            m11_004_certified=False,m11_004_evidence_fingerprint=FP4,
            m11_006_certified=True,m11_006_evidence_fingerprint=FP6,
            outcomes=[outcome(1)],registry=reg(),
        )
