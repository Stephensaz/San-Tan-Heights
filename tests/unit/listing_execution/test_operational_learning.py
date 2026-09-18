from dataclasses import replace
import pytest

from src.listing_execution.authorized_execution import ExecutionReceipt
from src.listing_execution.verification_reconciliation import ReconciliationCase, RollbackReceipt, VerificationReceipt
from src.listing_execution.operational_learning import (
    evaluate_operational_learning,
    load_operational_learning_registry,
    make_operational_episode,
    make_operational_outcome,
)

R="registries/listing_execution/m12-004-operational-learning-v1.0.yaml"

def reg(): return load_operational_learning_registry(R)

def receipt(*,outcome="SUCCEEDED",unknown=False,duplicate=False,attempted=True):
    return ExecutionReceipt(
        receipt_id="RC",request_id="REQ",request_fingerprint="1"*64,idempotency_key="2"*64,
        proposal_fingerprint="3"*64,authorized_action_fingerprint="4"*64,
        approval_fingerprint="5"*64,authority_fingerprint="6"*64,adapter_id="A",
        adapter_response_fingerprint="7"*64,outcome=outcome,external_receipt_id="EXT" if outcome=="SUCCEEDED" else None,
        side_effect_attempted=attempted,duplicate_suppressed=duplicate,outcome_unknown=unknown,
        recorded_at="2026-09-18T09:00:00-07:00",lineage_fingerprints=("1"*64,),immutable=True,
        public_eligible=False,receipt_fingerprint="8"*64,
    )

def verification(state="VERIFIED"):
    return VerificationReceipt(
        verification_id="V",execution_receipt_fingerprint="8"*64,observation_fingerprint="9"*64,
        verification_state=state,expected_outcome="SUCCEEDED",observed_state_code="APPLIED",
        reason_codes=(state,),verified_at="2026-09-18T09:05:00-07:00",immutable=True,
        verification_fingerprint="a"*64,
    )

def reconciliation(state="OPEN"):
    return ReconciliationCase(
        reconciliation_case_id="REC",execution_receipt_fingerprint="8"*64,
        verification_fingerprint="a"*64,state=state,reason_codes=("MISMATCH",),
        corrective_action_eligible=True,rollback_eligibility="ELIGIBLE",
        opened_at="2026-09-18T09:06:00-07:00",case_fingerprint="b"*64,
    )

def rollback(*,outcome="SUCCEEDED",unknown=False):
    return RollbackReceipt(
        rollback_receipt_id="RB",rollback_request_fingerprint="c"*64,idempotency_key="d"*64,
        reconciliation_case_fingerprint="b"*64,original_execution_receipt_fingerprint="8"*64,
        verification_fingerprint="a"*64,rollback_approval_fingerprint="e"*64,
        rollback_authority_fingerprint="f"*64,outcome=outcome,
        external_receipt_id="RB-EXT" if outcome=="SUCCEEDED" else None,
        side_effect_attempted=True,duplicate_suppressed=False,outcome_unknown=unknown,
        recorded_at="2026-09-18T09:10:00-07:00",immutable=True,receipt_fingerprint="0"*64,
    )

def episode(*,r=None,v=None,rec=None,rb=None,eid="E1"):
    r=r or receipt(); v=v or verification()
    return make_operational_episode(
        episode_id=eid,subject_property_id="SUB",listing_id="L",action_type="REFRESH_MARKET_EVIDENCE",
        proposal_fingerprint="3"*64,approval_fingerprint="5"*64,authority_fingerprint="6"*64,
        execution_receipt=r,verification=v,reconciliation_case=rec,rollback_receipt=rb,
    )

def outcome(ep,state="SUCCEEDED",oid="O1"):
    return make_operational_outcome(
        outcome_id=oid,episode_fingerprint=ep.episode_fingerprint,outcome_type="OPERATIONAL_RESULT",
        outcome_state=state,observed_at="2026-09-18T10:00:00-07:00",
        source_fingerprint="1"*64,notes_fingerprint="2"*64,registry=reg(),
    )

def test_learning_is_deterministic():
    e=episode(); o=outcome(e)
    assert evaluate_operational_learning(episodes=[e],outcomes=[o],registry=reg()).learning_fingerprint==evaluate_operational_learning(episodes=[e],outcomes=[o],registry=reg()).learning_fingerprint

def test_episode_requires_exact_proposal_approval_authority_lineage():
    r=receipt()
    with pytest.raises(ValueError,match="proposal lineage mismatch"):
        make_operational_episode(
            episode_id="E",subject_property_id="S",listing_id="L",action_type="X",
            proposal_fingerprint="9"*64,approval_fingerprint="5"*64,authority_fingerprint="6"*64,
            execution_receipt=r,verification=verification(),
        )

def test_verification_lineage_is_required():
    bad=replace(verification(),execution_receipt_fingerprint="9"*64)
    with pytest.raises(ValueError,match="verification lineage mismatch"):
        episode(v=bad)

def test_rollback_requires_reconciliation_case():
    with pytest.raises(ValueError,match="requires reconciliation case"):
        episode(rb=rollback())

def test_associations_are_explicitly_noncausal():
    e=episode(); result=evaluate_operational_learning(episodes=[e],outcomes=[outcome(e)],registry=reg())
    assert result.associations
    assert all(a.causal_claim is False for a in result.associations)
    assert all("does not establish causation" in a.statement for a in result.associations)

def test_metrics_measure_execution_and_verification():
    e=episode(); result=evaluate_operational_learning(episodes=[e],outcomes=[outcome(e)],registry=reg())
    m=result.metrics
    assert m.execution_attempt_count==1
    assert m.execution_success_count==1
    assert m.verification_count==1
    assert m.verification_mismatch_count==0

def test_duplicate_suppression_is_counted_without_policy_change():
    r=receipt(outcome="DUPLICATE_SUPPRESSED",duplicate=True,attempted=False)
    e=episode(r=r)
    result=evaluate_operational_learning(episodes=[e],outcomes=[outcome(e,"DUPLICATE_SUPPRESSED")],registry=reg())
    assert result.metrics.duplicate_suppression_count==1
    assert result.external_action_capability=="NONE"

def test_execution_unknown_remains_explicit_and_creates_advisory_candidate():
    r=receipt(outcome="OUTCOME_UNKNOWN",unknown=True)
    e=episode(r=r,v=verification("OUTCOME_UNKNOWN"))
    o=outcome(e,"OUTCOME_UNKNOWN")
    result=evaluate_operational_learning(episodes=[e],outcomes=[o],registry=reg())
    assert result.unknown_outcome_ids==("O1",)
    c=[x for x in result.improvement_candidates if x.trigger_code=="EXECUTION_OUTCOME_UNKNOWN"][0]
    assert c.advisory_only is True
    assert c.promotion_status=="NOT_PROMOTED"

def test_verification_mismatch_creates_policy_review_candidate():
    e=episode(v=verification("MISMATCH"),rec=reconciliation())
    result=evaluate_operational_learning(episodes=[e],outcomes=[outcome(e,"MISMATCH")],registry=reg())
    assert result.metrics.verification_mismatch_count==1
    assert any(c.candidate_type=="VERIFICATION_POLICY_REVIEW" for c in result.improvement_candidates)

def test_open_reconciliation_is_measured_and_advisory():
    e=episode(v=verification("MISMATCH"),rec=reconciliation())
    result=evaluate_operational_learning(episodes=[e],outcomes=[outcome(e,"UNRESOLVED")],registry=reg())
    assert result.metrics.open_reconciliation_count==1
    assert "O1" in result.unknown_outcome_ids
    assert any(c.candidate_type=="RECONCILIATION_WORKFLOW_REVIEW" for c in result.improvement_candidates)

def test_rollback_success_is_measured():
    e=episode(v=verification("MISMATCH"),rec=reconciliation(),rb=rollback())
    result=evaluate_operational_learning(episodes=[e],outcomes=[outcome(e,"RESOLVED")],registry=reg())
    assert result.metrics.rollback_attempt_count==1
    assert result.metrics.rollback_success_count==1

def test_rollback_unknown_creates_advisory_reliability_candidate():
    rb=rollback(outcome="OUTCOME_UNKNOWN",unknown=True)
    e=episode(v=verification("MISMATCH"),rec=reconciliation(),rb=rb)
    result=evaluate_operational_learning(episodes=[e],outcomes=[outcome(e,"OUTCOME_UNKNOWN")],registry=reg())
    assert result.metrics.rollback_outcome_unknown_count==1
    assert any(c.candidate_type=="ROLLBACK_RELIABILITY_REVIEW" and c.advisory_only for c in result.improvement_candidates)

def test_outcome_must_link_to_known_episode():
    e=episode()
    bad=make_operational_outcome(
        outcome_id="O",episode_fingerprint="f"*64,outcome_type="OPERATIONAL_RESULT",
        outcome_state="SUCCEEDED",observed_at="2026-09-18T10:00:00-07:00",
        source_fingerprint="1"*64,notes_fingerprint="2"*64,registry=reg(),
    )
    with pytest.raises(ValueError,match="episode lineage mismatch"):
        evaluate_operational_learning(episodes=[e],outcomes=[bad],registry=reg())

def test_unknown_and_missing_states_are_not_collapsed_into_success():
    e=episode()
    o=outcome(e,"OUTCOME_UNKNOWN")
    result=evaluate_operational_learning(episodes=[e],outcomes=[o],registry=reg())
    assert result.unknown_outcome_ids==("O1",)
    assert result.metrics.execution_success_count==1

def test_candidate_language_is_advisory_noncausal_no_live_change():
    e=episode(v=verification("MISMATCH"),rec=reconciliation())
    result=evaluate_operational_learning(episodes=[e],outcomes=[outcome(e,"MISMATCH")],registry=reg())
    assert all(c.advisory_only and c.promotion_status=="NOT_PROMOTED" for c in result.improvement_candidates)
    assert all("does not establish causation" in c.rationale for c in result.improvement_candidates)
    assert result.public_eligible is False
    assert result.external_action_capability=="NONE"

def test_duplicate_episode_or_outcome_ids_fail_closed():
    e=episode()
    o=outcome(e)
    with pytest.raises(ValueError,match="duplicate operational episode_id"):
        evaluate_operational_learning(episodes=[e,e],outcomes=[o],registry=reg())
    with pytest.raises(ValueError,match="duplicate operational outcome_id"):
        evaluate_operational_learning(episodes=[e],outcomes=[o,o],registry=reg())
