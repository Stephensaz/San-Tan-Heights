import pytest

from src.listing_execution.operational_learning import OperationalImprovementCandidate
from src.listing_execution.policy_calibration import (
    build_accepted_policy_baseline,
    build_policy_candidate,
    build_policy_fixture,
    evaluate_policy_candidate,
    load_policy_calibration_registry,
    make_policy_promotion_approval,
)

R="registries/listing_execution/m12-005-policy-calibration-v1.0.yaml"

def reg(): return load_policy_calibration_registry(R)

def improvement(candidate_type="EXECUTION_RELIABILITY_REVIEW"):
    return OperationalImprovementCandidate(
        candidate_id="I-1",
        candidate_type=candidate_type,
        trigger_code="EXECUTION_OUTCOME_UNKNOWN",
        source_fingerprints=("1"*64,),
        rationale="Advisory only",
        advisory_only=True,
        promotion_status="NOT_PROMOTED",
        candidate_fingerprint="2"*64,
    )

def baseline(): return build_accepted_policy_baseline(reg())

def fixtures():
    return [
        build_policy_fixture(
            fixture_id="F-EXEC",domain="EXECUTION",
            protected_control_expectations=(
                "human_approval_required",
                "independent_authority_required",
                "authority_revalidation_required",
                "deterministic_idempotency_required",
                "outcome_unknown_silent_retry_prohibited",
            ),registry=reg(),
        ),
        build_policy_fixture(
            fixture_id="F-VERIFY",domain="VERIFICATION",
            protected_control_expectations=(
                "independent_verification_required",
                "mismatch_reconciliation_required",
                "outcome_unknown_reconciliation_required",
            ),registry=reg(),
        ),
        build_policy_fixture(
            fixture_id="F-ROLLBACK",domain="ROLLBACK",
            protected_control_expectations=(
                "separate_rollback_approval_required",
                "separate_rollback_authority_required",
                "rollback_authority_revalidation_required",
            ),registry=reg(),
        ),
    ]

def test_baseline_is_deterministic_and_not_candidate():
    a=baseline(); b=baseline()
    assert a.policy_fingerprint==b.policy_fingerprint
    assert a.isolated_candidate is False
    assert a.parent_version_id is None

def test_candidate_is_isolated_and_exact_parent_bound():
    b=baseline()
    c=build_policy_candidate(
        candidate_version_id="C-1",improvement_candidate=improvement(),
        domain="EXECUTION",baseline=b,
        policy_changes={"immutable_execution_receipt_required":True},registry=reg(),
    )
    assert c.isolated_candidate is True
    assert c.parent_version_id==b.version_id
    assert c.parent_fingerprint==b.policy_fingerprint
    assert b.policy_values==baseline().policy_values

def test_candidate_type_must_be_eligible_for_domain():
    with pytest.raises(ValueError,match="not eligible"):
        build_policy_candidate(
            candidate_version_id="C-1",improvement_candidate=improvement("VERIFICATION_POLICY_REVIEW"),
            domain="EXECUTION",baseline=baseline(),
            policy_changes={"independent_verification_required":True},registry=reg(),
        )

def test_unsupported_policy_field_fails_closed():
    with pytest.raises(ValueError,match="unsupported policy field"):
        build_policy_candidate(
            candidate_version_id="C-1",improvement_candidate=improvement(),
            domain="EXECUTION",baseline=baseline(),
            policy_changes={"auto_execute_without_approval":True},registry=reg(),
        )

def test_side_effect_free_replay_never_mutates_baseline():
    b=baseline(); original=b.policy_values
    c=build_policy_candidate(
        candidate_version_id="C-1",improvement_candidate=improvement(),
        domain="EXECUTION",baseline=b,
        policy_changes={"immutable_execution_receipt_required":True},registry=reg(),
    )
    evaluate_policy_candidate(baseline=b,candidate=c,fixtures=fixtures(),registry=reg())
    assert b.policy_values==original

def test_current_vs_candidate_differences_are_explicit():
    b=baseline()
    c=build_policy_candidate(
        candidate_version_id="C-1",improvement_candidate=improvement(),
        domain="EXECUTION",baseline=b,
        policy_changes={"immutable_execution_receipt_required":False},registry=reg(),
    )
    result=evaluate_policy_candidate(baseline=b,candidate=c,fixtures=fixtures(),registry=reg())
    assert any("immutable_execution_receipt_required" in x.changed_fields for x in result.comparisons)

def test_human_approval_regression_blocks_promotion():
    b=baseline()
    c=build_policy_candidate(
        candidate_version_id="C-BAD",improvement_candidate=improvement(),
        domain="EXECUTION",baseline=b,
        policy_changes={"human_approval_required":False},registry=reg(),
    )
    a=make_policy_promotion_approval(
        approval_id="A",candidate_policy_fingerprint=c.policy_fingerprint,
        authority_id="H",status="APPROVED",
    )
    result=evaluate_policy_candidate(baseline=b,candidate=c,fixtures=fixtures(),registry=reg(),promotion_approval=a)
    assert result.safety_regression_count>0
    assert result.promotion_package is None

@pytest.mark.parametrize("field",[
    "independent_authority_required",
    "authority_revalidation_required",
    "deterministic_idempotency_required",
    "duplicate_side_effect_suppression_required",
    "outcome_unknown_silent_retry_prohibited",
    "independent_verification_required",
    "mismatch_reconciliation_required",
    "outcome_unknown_reconciliation_required",
    "separate_rollback_approval_required",
    "separate_rollback_authority_required",
    "rollback_authority_revalidation_required",
    "immutable_execution_receipt_required",
    "immutable_verification_receipt_required",
    "immutable_rollback_receipt_required",
    "seller_approval_inference_prohibited",
    "system_determined_price_or_terms_prohibited",
    "public_strategy_exposure_prohibited",
])
def test_every_protected_control_fails_closed_if_weakened(field):
    b=baseline()
    c=build_policy_candidate(
        candidate_version_id="C-BAD",improvement_candidate=improvement(),
        domain="EXECUTION",baseline=b,policy_changes={field:False},registry=reg(),
    )
    result=evaluate_policy_candidate(baseline=b,candidate=c,fixtures=fixtures(),registry=reg())
    assert result.safety_regression_count>0
    assert result.promotion_package is None

def test_no_auto_promotion_without_separate_approval():
    b=baseline()
    c=build_policy_candidate(
        candidate_version_id="C-1",improvement_candidate=improvement(),
        domain="EXECUTION",baseline=b,
        policy_changes={"immutable_execution_receipt_required":True},registry=reg(),
    )
    result=evaluate_policy_candidate(baseline=b,candidate=c,fixtures=fixtures(),registry=reg())
    assert result.approval_required is True
    assert result.promotion_package is None

def test_pending_or_rejected_approval_never_creates_package():
    b=baseline()
    c=build_policy_candidate(
        candidate_version_id="C-1",improvement_candidate=improvement(),
        domain="EXECUTION",baseline=b,
        policy_changes={"immutable_execution_receipt_required":True},registry=reg(),
    )
    for status in ("PENDING","REJECTED"):
        a=make_policy_promotion_approval(
            approval_id=status,candidate_policy_fingerprint=c.policy_fingerprint,
            authority_id="H",status=status,
        )
        assert evaluate_policy_candidate(
            baseline=b,candidate=c,fixtures=fixtures(),registry=reg(),promotion_approval=a
        ).promotion_package is None

def test_approved_nonregressive_candidate_creates_controlled_package_with_rollback():
    b=baseline()
    c=build_policy_candidate(
        candidate_version_id="C-1",improvement_candidate=improvement(),
        domain="EXECUTION",baseline=b,
        policy_changes={"immutable_execution_receipt_required":True},registry=reg(),
    )
    a=make_policy_promotion_approval(
        approval_id="APPROVED",candidate_policy_fingerprint=c.policy_fingerprint,
        authority_id="H",status="APPROVED",
    )
    result=evaluate_policy_candidate(baseline=b,candidate=c,fixtures=fixtures(),registry=reg(),promotion_approval=a)
    pkg=result.promotion_package
    assert pkg is not None
    assert pkg.status=="READY_FOR_M12_CERTIFICATION"
    assert pkg.rollback_version_id==b.version_id
    assert pkg.rollback_policy_fingerprint==b.policy_fingerprint
    assert pkg.public_eligible is False
    assert pkg.external_action_capability=="NONE"

def test_wrong_approval_candidate_fingerprint_fails_closed():
    b=baseline()
    c=build_policy_candidate(
        candidate_version_id="C-1",improvement_candidate=improvement(),
        domain="EXECUTION",baseline=b,
        policy_changes={"immutable_execution_receipt_required":True},registry=reg(),
    )
    a=make_policy_promotion_approval(
        approval_id="A",candidate_policy_fingerprint="9"*64,authority_id="H",status="APPROVED",
    )
    with pytest.raises(ValueError,match="approval candidate fingerprint mismatch"):
        evaluate_policy_candidate(baseline=b,candidate=c,fixtures=fixtures(),registry=reg(),promotion_approval=a)

def test_replay_is_deterministic_and_fixture_order_independent():
    b=baseline()
    c=build_policy_candidate(
        candidate_version_id="C-1",improvement_candidate=improvement(),
        domain="EXECUTION",baseline=b,
        policy_changes={"immutable_execution_receipt_required":True},registry=reg(),
    )
    a=evaluate_policy_candidate(baseline=b,candidate=c,fixtures=fixtures(),registry=reg())
    z=evaluate_policy_candidate(baseline=b,candidate=c,fixtures=reversed(fixtures()),registry=reg())
    assert a.evaluation_fingerprint==z.evaluation_fingerprint
