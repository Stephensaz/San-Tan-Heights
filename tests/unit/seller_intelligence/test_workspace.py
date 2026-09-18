import pytest

from src.seller_intelligence.opportunity import GovernedAlternativeInput, build_seller_opportunity, load_seller_opportunity_registry
from src.seller_intelligence.strategy import GovernedStrategyFinding, build_property_seller_strategy, load_seller_strategy_registry
from src.seller_intelligence.scenario import ScenarioAssumption, evaluate_seller_scenario, load_seller_scenario_registry
from src.seller_intelligence.timeline import GovernedTimelineSnapshot, build_seller_decision_timeline, load_seller_timeline_registry
from src.seller_intelligence.communication import translate_seller_intelligence, load_communication_registry
from src.seller_intelligence.workspace import build_seller_intelligence_case, load_workspace_registry, make_human_decision

O="registries/seller_intelligence/m11-001-seller-opportunity-v1.0.yaml"
S="registries/seller_intelligence/m11-002-property-seller-strategy-v1.0.yaml"
SC="registries/seller_intelligence/m11-003-seller-scenario-sensitivity-v1.0.yaml"
T="registries/seller_intelligence/m11-004-seller-decision-timeline-v1.0.yaml"
C="registries/seller_intelligence/m11-005-communication-translation-v1.0.yaml"
W="registries/seller_intelligence/m11-006-seller-workspace-v1.0.yaml"
FP1="a"*64; FP2="b"*64; FP3="c"*64; FP4="d"*64; FP5="e"*64


def inputs():
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
        findings=[
            GovernedStrategyFinding("P-1","SUBJECT-1","BUYER_DEPTH","DEEP","Prior",True,"PASS","SELLER","CURRENT","3"*64),
        ],registry=load_seller_strategy_registry(S),
    )
    strat=build_property_seller_strategy(
        opportunity=opp,m11_001_certified=True,m11_001_evidence_fingerprint=FP1,
        findings=[
            GovernedStrategyFinding("F-1","SUBJECT-1","BUYER_DEPTH","THIN","Current",True,"PASS","SELLER","CURRENT","4"*64),
        ],registry=load_seller_strategy_registry(S),
    )
    scen=evaluate_seller_scenario(
        scenario_id="SC-1",strategy=strat,m11_002_certified=True,m11_002_evidence_fingerprint=FP2,
        assumptions=[ScenarioAssumption("H-1","SUBJECT-1","BUYER_DEPTH","DEEP","What if improves",True)],
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
        m11_001_evidence_fingerprint=FP1,m11_002_evidence_fingerprint=FP2,
        m11_003_evidence_fingerprint=FP3,m11_004_evidence_fingerprint=FP4,
        registry=load_communication_registry(C),
    )
    return opp,strat,scen,timeline,comm


def reg(): return load_workspace_registry(W)


def build(decisions=()):
    opp,strat,scen,timeline,comm=inputs()
    return build_seller_intelligence_case(
        case_id="CASE-1",opportunity=opp,strategy=strat,scenario=scen,timeline=timeline,communication=comm,
        m11_001_certified=True,m11_002_certified=True,m11_003_certified=True,m11_004_certified=True,m11_005_certified=True,
        m11_001_evidence_fingerprint=FP1,m11_002_evidence_fingerprint=FP2,m11_003_evidence_fingerprint=FP3,
        m11_004_evidence_fingerprint=FP4,m11_005_evidence_fingerprint=FP5,
        human_decisions=decisions,registry=reg(),
    )


def test_workspace_is_deterministic():
    assert build().case_fingerprint==build().case_fingerprint


def test_current_artifacts_cover_m11_001_through_005():
    types={x.artifact_type for x in build().current_artifacts}
    assert types=={"M11-001_OPPORTUNITY","M11-002_STRATEGY","M11-003_SCENARIO","M11-004_TIMELINE","M11-005_COMMUNICATION"}


def test_superseded_strategy_snapshot_remains_visible():
    case=build()
    assert case.superseded_artifacts
    assert all(x.status=="SUPERSEDED" for x in case.superseded_artifacts)


def test_open_monitoring_event_becomes_pending_review_item():
    case=build()
    assert any(x.status=="PENDING" for x in case.review_items)
    assert case.next_safe_step=="REVIEW_PENDING_ITEM"


def test_acknowledgement_requires_explicit_human_decision():
    base=build()
    item=base.review_items[0]
    d=make_human_decision(
        decision_id="D-1",review_item_id=item.review_item_id,decision_type="ACKNOWLEDGE_REVIEW",
        actor_id="USER-1",decided_at="2026-09-08T10:00:00-07:00",rationale="Reviewed evidence",registry=reg(),
    )
    case=build([d])
    assert case.review_items[0].status=="ACKNOWLEDGED"
    assert case.review_items[0].acknowledged_by_decision_id=="D-1"


def test_resolution_requires_explicit_human_decision():
    item=build().review_items[0]
    d=make_human_decision(
        decision_id="D-2",review_item_id=item.review_item_id,decision_type="RESOLVE_REVIEW",
        actor_id="USER-1",decided_at="2026-09-08T11:00:00-07:00",rationale="Review complete",registry=reg(),
    )
    case=build([d])
    assert case.review_items[0].status=="RESOLVED"
    assert case.next_safe_step=="NO_ACTION_REQUIRED"


def test_human_decisions_are_separate_from_machine_artifacts():
    item=build().review_items[0]
    d=make_human_decision(
        decision_id="D-3",review_item_id=item.review_item_id,decision_type="DEFER_REVIEW",
        actor_id="USER-1",decided_at="2026-09-08T12:00:00-07:00",rationale="Need more evidence",registry=reg(),
    )
    case=build([d])
    assert case.human_decisions[0].decision_id=="D-3"
    assert all("D-3" not in x.artifact_fingerprint for x in case.current_artifacts)


def test_duplicate_decision_id_fails_closed():
    d=make_human_decision(
        decision_id="D-X",review_item_id=None,decision_type="RECORD_NOTE",
        actor_id="USER-1",decided_at="2026-09-08T12:00:00-07:00",rationale="Note",registry=reg(),
    )
    with pytest.raises(ValueError,match="duplicate human decision_id"):
        build([d,d])


def test_naive_human_decision_timestamp_rejected():
    with pytest.raises(ValueError,match="must include timezone"):
        make_human_decision(
            decision_id="D-X",review_item_id=None,decision_type="RECORD_NOTE",
            actor_id="USER-1",decided_at="2026-09-08T12:00:00",rationale="Note",registry=reg(),
        )


def test_review_decision_without_item_id_rejected():
    with pytest.raises(ValueError,match="review decision requires review_item_id"):
        make_human_decision(
            decision_id="D-X",review_item_id=None,decision_type="RESOLVE_REVIEW",
            actor_id="USER-1",decided_at="2026-09-08T12:00:00-07:00",rationale="Resolve",registry=reg(),
        )


def test_limitations_remain_visible():
    case=build()
    assert isinstance(case.limitations,tuple)


def test_workspace_is_internal_nonpublic_no_action():
    case=build()
    assert case.output_tier=="INTERNAL"
    assert case.public_eligible is False
    assert case.external_action_capability=="NONE"


def test_case_id_required():
    opp,strat,scen,timeline,comm=inputs()
    with pytest.raises(ValueError,match="case_id required"):
        build_seller_intelligence_case(
            case_id="",opportunity=opp,strategy=strat,scenario=scen,timeline=timeline,communication=comm,
            m11_001_certified=True,m11_002_certified=True,m11_003_certified=True,m11_004_certified=True,m11_005_certified=True,
            m11_001_evidence_fingerprint=FP1,m11_002_evidence_fingerprint=FP2,m11_003_evidence_fingerprint=FP3,
            m11_004_evidence_fingerprint=FP4,m11_005_evidence_fingerprint=FP5,registry=reg(),
        )


def test_uncertified_parent_fails_closed():
    opp,strat,scen,timeline,comm=inputs()
    with pytest.raises(ValueError,match="certified M11-001, M11-002, M11-004, and M11-005 inputs required"):
        build_seller_intelligence_case(
            case_id="CASE-1",opportunity=opp,strategy=strat,scenario=scen,timeline=timeline,communication=comm,
            m11_001_certified=True,m11_002_certified=False,m11_003_certified=True,m11_004_certified=True,m11_005_certified=True,
            m11_001_evidence_fingerprint=FP1,m11_002_evidence_fingerprint=FP2,m11_003_evidence_fingerprint=FP3,
            m11_004_evidence_fingerprint=FP4,m11_005_evidence_fingerprint=FP5,registry=reg(),
        )
