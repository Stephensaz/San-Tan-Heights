import pytest

from src.seller_intelligence.effectiveness import CalibrationCandidate
from src.seller_intelligence.calibration import (
    build_accepted_baseline,
    build_fixture,
    build_candidate_version,
    evaluate_candidate,
    load_calibration_registry,
    make_promotion_approval,
)

R="registries/seller_intelligence/m11-008-calibration-promotion-v1.0.yaml"


def reg():
    return load_calibration_registry(R)


def advisory(candidate_type="REVIEW_CONDITION_CALIBRATION"):
    return CalibrationCandidate(
        candidate_id="CAL-1",
        candidate_type=candidate_type,
        outcome_id="O-1",
        rationale="Advisory only",
        advisory_only=True,
        promotion_status="NOT_PROMOTED",
        source_fingerprints=("1"*64,),
        candidate_fingerprint="2"*64,
    )


def fixtures():
    return [
        build_fixture(
            fixture_id="F-1",competitive_pressure="HIGH",buyer_depth="THIN",
            pricing_response_environment="WEAK",new_construction_pressure="HIGH",
            verified_differentiation="LIMITED",week_over_week_direction="WORSENING",
            protected_behavior=True,
        ),
        build_fixture(
            fixture_id="F-2",competitive_pressure="LOW",buyer_depth="DEEP",
            pricing_response_environment="MIXED",new_construction_pressure="LOW",
            verified_differentiation="STRONG",week_over_week_direction="STABLE",
            protected_behavior=False,
        ),
    ]


def test_accepted_baseline_is_deterministic_and_immutable_model():
    a=build_accepted_baseline(reg())
    b=build_accepted_baseline(reg())
    assert a.rule_fingerprint==b.rule_fingerprint
    assert a.isolated_candidate is False
    assert a.parent_version_id is None


def test_candidate_is_isolated_and_exactly_bound_to_parent():
    base=build_accepted_baseline(reg())
    c=build_candidate_version(
        candidate_id="CAND-1",advisory_candidate=advisory(),baseline=base,
        rule_changes={"DAY_10_MIXED_RESPONSE_REVIEW_ENABLED":True},registry=reg(),
    )
    assert c.isolated_candidate is True
    assert c.parent_version_id==base.version_id
    assert c.parent_fingerprint==base.rule_fingerprint
    assert dict(base.rules)["DAY_10_MIXED_RESPONSE_REVIEW_ENABLED"] is False
    assert dict(c.rules)["DAY_10_MIXED_RESPONSE_REVIEW_ENABLED"] is True


def test_side_effect_free_replay_does_not_mutate_baseline():
    base=build_accepted_baseline(reg())
    original=base.rules
    c=build_candidate_version(
        candidate_id="CAND-1",advisory_candidate=advisory(),baseline=base,
        rule_changes={"DAY_10_MIXED_RESPONSE_REVIEW_ENABLED":True},registry=reg(),
    )
    evaluate_candidate(baseline=base,candidate=c,fixtures=fixtures(),registry=reg())
    assert base.rules==original


def test_current_vs_candidate_changes_are_explicit():
    base=build_accepted_baseline(reg())
    c=build_candidate_version(
        candidate_id="CAND-1",advisory_candidate=advisory(),baseline=base,
        rule_changes={"DAY_10_MIXED_RESPONSE_REVIEW_ENABLED":True},registry=reg(),
    )
    result=evaluate_candidate(baseline=base,candidate=c,fixtures=fixtures(),registry=reg())
    f2=[x for x in result.comparisons if x.fixture_id=="F-2"][0]
    assert 10 in f2.changed_days
    assert f2.communication_effect=="ADDED_REVIEW_GUIDANCE"
    assert result.changed_fixture_count==1


def test_protected_regression_fails_closed_and_blocks_package():
    base=build_accepted_baseline(reg())
    c=build_candidate_version(
        candidate_id="CAND-BAD",advisory_candidate=advisory(),baseline=base,
        rule_changes={"DAY_7_HIGH_PRESSURE_REVIEW_ENABLED":False},registry=reg(),
    )
    approval=make_promotion_approval(
        approval_id="A-1",candidate_rule_fingerprint=c.rule_fingerprint,
        authority_id="HUMAN-1",status="APPROVED",
    )
    result=evaluate_candidate(baseline=base,candidate=c,fixtures=fixtures(),registry=reg(),approval=approval)
    assert result.regression_count>0
    assert result.promotion_package is None


def test_day14_regression_is_always_blocking():
    base=build_accepted_baseline(reg())
    c=build_candidate_version(
        candidate_id="CAND-BAD",advisory_candidate=advisory(),baseline=base,
        rule_changes={"DAY_14_ALWAYS_REVIEW_ENABLED":False},registry=reg(),
    )
    result=evaluate_candidate(baseline=base,candidate=c,fixtures=fixtures(),registry=reg())
    assert result.regression_count==2
    assert all("DAY_14_ALWAYS_REVIEW_REGRESSION" in x.regression_reasons for x in result.comparisons)


def test_no_auto_promotion_without_human_approval():
    base=build_accepted_baseline(reg())
    c=build_candidate_version(
        candidate_id="CAND-1",advisory_candidate=advisory(),baseline=base,
        rule_changes={"DAY_10_MIXED_RESPONSE_REVIEW_ENABLED":True},registry=reg(),
    )
    result=evaluate_candidate(baseline=base,candidate=c,fixtures=fixtures(),registry=reg())
    assert result.regression_count==0
    assert result.approval_required is True
    assert result.promotion_package is None


def test_pending_or_rejected_approval_does_not_create_package():
    base=build_accepted_baseline(reg())
    c=build_candidate_version(
        candidate_id="CAND-1",advisory_candidate=advisory(),baseline=base,
        rule_changes={"DAY_10_MIXED_RESPONSE_REVIEW_ENABLED":True},registry=reg(),
    )
    for status in ("PENDING","REJECTED"):
        approval=make_promotion_approval(
            approval_id=f"A-{status}",candidate_rule_fingerprint=c.rule_fingerprint,
            authority_id="HUMAN-1",status=status,
        )
        result=evaluate_candidate(baseline=base,candidate=c,fixtures=fixtures(),registry=reg(),approval=approval)
        assert result.promotion_package is None


def test_approved_nonregressive_candidate_creates_m11_009_package():
    base=build_accepted_baseline(reg())
    c=build_candidate_version(
        candidate_id="CAND-1",advisory_candidate=advisory(),baseline=base,
        rule_changes={"DAY_10_MIXED_RESPONSE_REVIEW_ENABLED":True},registry=reg(),
    )
    approval=make_promotion_approval(
        approval_id="A-APPROVED",candidate_rule_fingerprint=c.rule_fingerprint,
        authority_id="HUMAN-1",status="APPROVED",
    )
    result=evaluate_candidate(baseline=base,candidate=c,fixtures=fixtures(),registry=reg(),approval=approval)
    pkg=result.promotion_package
    assert pkg is not None
    assert pkg.status=="READY_FOR_M11_009_CERTIFICATION"
    assert pkg.rollback_version_id==base.version_id
    assert pkg.rollback_rule_fingerprint==base.rule_fingerprint
    assert pkg.public_eligible is False
    assert pkg.external_action_capability=="NONE"


def test_wrong_approval_fingerprint_fails_closed():
    base=build_accepted_baseline(reg())
    c=build_candidate_version(
        candidate_id="CAND-1",advisory_candidate=advisory(),baseline=base,
        rule_changes={"DAY_10_MIXED_RESPONSE_REVIEW_ENABLED":True},registry=reg(),
    )
    approval=make_promotion_approval(
        approval_id="A-1",candidate_rule_fingerprint="9"*64,
        authority_id="HUMAN-1",status="APPROVED",
    )
    with pytest.raises(ValueError,match="approval candidate fingerprint mismatch"):
        evaluate_candidate(baseline=base,candidate=c,fixtures=fixtures(),registry=reg(),approval=approval)


def test_unknown_outcome_coverage_candidate_cannot_create_rule_version():
    base=build_accepted_baseline(reg())
    with pytest.raises(ValueError,match="unsupported M11-007 calibration candidate type"):
        build_candidate_version(
            candidate_id="CAND-1",advisory_candidate=advisory("OUTCOME_COVERAGE_GAP"),baseline=base,
            rule_changes={"DAY_10_MIXED_RESPONSE_REVIEW_ENABLED":True},registry=reg(),
        )


def test_unsupported_rule_change_fails_closed():
    base=build_accepted_baseline(reg())
    with pytest.raises(ValueError,match="unsupported rule"):
        build_candidate_version(
            candidate_id="CAND-1",advisory_candidate=advisory(),baseline=base,
            rule_changes={"RECOMMENDED_LIST_PRICE_ENABLED":True},registry=reg(),
        )


def test_evaluation_is_deterministic_and_fixture_order_independent():
    base=build_accepted_baseline(reg())
    c=build_candidate_version(
        candidate_id="CAND-1",advisory_candidate=advisory(),baseline=base,
        rule_changes={"DAY_10_MIXED_RESPONSE_REVIEW_ENABLED":True},registry=reg(),
    )
    a=evaluate_candidate(baseline=base,candidate=c,fixtures=fixtures(),registry=reg())
    b=evaluate_candidate(baseline=base,candidate=c,fixtures=reversed(fixtures()),registry=reg())
    assert a.evaluation_fingerprint==b.evaluation_fingerprint
