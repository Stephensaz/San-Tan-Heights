import pytest

from src.seller_intelligence.workspace import ReviewItem, SellerIntelligenceCase
from src.listing_execution.action_planning import (
    build_governed_action_proposal, load_action_proposal_registry,
    make_action_intent, make_listing_context,
)
from src.listing_execution.authorized_execution import (
    authorize_action, build_execution_request, execute_authorized_action,
    load_execution_registry, make_adapter_response, make_execution_authority,
    make_human_approval,
)

P="registries/listing_execution/m12-001-action-proposal-v1.0.yaml"
E="registries/listing_execution/m12-002-authorized-execution-v1.0.yaml"
M11_ROOT="8c5c656934909c10c3c5bc52ae9d12b3c646348686f3d1d787a9b0b067ce6ccf"


def preg(): return load_action_proposal_registry(P)
def ereg(): return load_execution_registry(E)


def proposal():
    c=SellerIntelligenceCase(
        case_id="CASE-1",subject_property_id="SUBJECT-1",current_artifacts=(),
        superseded_artifacts=(),
        review_items=(ReviewItem(
            review_item_id="REVIEW-1",source_event_fingerprint="1"*64,snapshot_id="S-1",
            status="PENDING",reasons=("PRESSURE",),acknowledged_by_decision_id=None,
            resolved_by_decision_id=None,review_item_fingerprint="2"*64,
        ),),
        human_decisions=(),limitations=(),next_safe_step="REVIEW_PENDING_ITEM",
        output_tier="INTERNAL",public_eligible=False,external_action_capability="NONE",
        case_fingerprint="3"*64,
    )
    context=make_listing_context(
        listing_id="LISTING-1",subject_property_id="SUBJECT-1",listing_status="ACTIVE",
        freshness_state="CURRENT",observed_at="2026-09-18T09:00:00-07:00",
        source_fingerprint="4"*64,registry=preg(),
    )
    intent=make_action_intent(
        intent_id="I-1",subject_property_id="SUBJECT-1",
        action_type="REFRESH_MARKET_EVIDENCE",origin="SYSTEM_SIGNAL",
        target_review_item_id="REVIEW-1",requested_at="2026-09-18T09:01:00-07:00",
        requested_policy_version="LISTING-ACTION-PROPOSAL-v1.0",registry=preg(),
    )
    return build_governed_action_proposal(
        proposal_id="PROP-1",case=c,m11_release_certified=True,
        m11_release_evidence_fingerprint="5"*64,
        m11_release_certification_root=M11_ROOT,
        listing_context=context,intent=intent,registry=preg(),
    )


def approval(p=None, decision="APPROVED"):
    p=p or proposal()
    return make_human_approval(
        approval_id="APP-1",proposal_fingerprint=p.proposal_fingerprint,actor_id="HUMAN-1",
        decision=decision,approved_at="2026-09-18T09:05:00-07:00",
        rationale_fingerprint="6"*64,registry=ereg(),
    )


def authority(action_types=("REFRESH_MARKET_EVIDENCE",), *, status="VALID", end="2026-09-18T12:00:00-07:00"):
    return make_execution_authority(
        authority_id="AUTH-1",principal_id="HUMAN-1",listing_id="LISTING-1",
        allowed_action_types=action_types,status=status,
        valid_from="2026-09-18T08:00:00-07:00",valid_until=end,
        source_fingerprint="7"*64,registry=ereg(),
    )


def authorized(p=None,a=None,auth=None):
    p=p or proposal(); a=a or approval(p); auth=auth or authority()
    return authorize_action(
        authorized_action_id="AA-1",proposal=p,approval=a,authority=auth,
        authorized_at="2026-09-18T09:06:00-07:00",registry=ereg(),
    )


def request(aa=None):
    aa=aa or authorized()
    return build_execution_request(
        request_id="REQ-1",authorized_action=aa,adapter_id="TEST-ADAPTER",
        requested_at="2026-09-18T09:07:00-07:00",
    )


def success_adapter(req):
    return make_adapter_response(
        adapter_id=req.adapter_id,request_fingerprint=req.request_fingerprint,
        outcome="SUCCEEDED",external_receipt_id="EXT-1",registry=ereg(),
    )


def execute(*, p=None,a=None,auth=None,aa=None,req=None,adapter=success_adapter,prior=()):
    p=p or proposal(); a=a or approval(p); auth=auth or authority()
    aa=aa or authorized(p,a,auth); req=req or request(aa)
    return execute_authorized_action(
        receipt_id="RCPT-1",proposal=p,approval=a,authority=auth,
        authorized_action=aa,request=req,adapter=adapter,prior_receipts=prior,
        execution_at="2026-09-18T09:08:00-07:00",registry=ereg(),
    )


def test_authorization_requires_exact_explicit_human_approval():
    p=proposal()
    with pytest.raises(ValueError,match="explicit APPROVED"):
        authorized(p=p,a=approval(p,"REJECTED"))


def test_approval_must_bind_exact_proposal():
    p=proposal()
    bad=make_human_approval(
        approval_id="APP-X",proposal_fingerprint="9"*64,actor_id="HUMAN-1",
        decision="APPROVED",approved_at="2026-09-18T09:05:00-07:00",
        rationale_fingerprint="6"*64,registry=ereg(),
    )
    with pytest.raises(ValueError,match="exact proposal"):
        authorized(p=p,a=bad)


def test_authority_is_independent_and_scope_checked():
    p=proposal(); a=approval(p)
    with pytest.raises(ValueError,match="action scope mismatch"):
        authorized(p=p,a=a,auth=authority(("REVIEW_MARKETING_PLAN",)))


def test_expired_authority_fails_at_authorization():
    p=proposal(); a=approval(p)
    with pytest.raises(ValueError,match="not valid"):
        authorized(p=p,a=a,auth=authority(end="2026-09-18T09:05:30-07:00"))


def test_authorized_action_is_deterministic_and_nonpublic():
    p=proposal(); a=approval(p); auth=authority()
    x=authorized(p,a,auth); y=authorized(p,a,auth)
    assert x.authorized_action_fingerprint==y.authorized_action_fingerprint
    assert x.authorization_state=="AUTHORIZED"
    assert x.execution_state=="READY_FOR_EXECUTION"
    assert x.public_eligible is False


def test_idempotency_key_is_deterministic():
    aa=authorized()
    assert request(aa).idempotency_key==request(aa).idempotency_key


def test_successful_execution_has_immutable_receipt_and_external_receipt():
    r=execute()
    assert r.outcome=="SUCCEEDED"
    assert r.external_receipt_id=="EXT-1"
    assert r.side_effect_attempted is True
    assert r.duplicate_suppressed is False
    assert r.immutable is True
    assert r.public_eligible is False


def test_success_without_external_receipt_becomes_outcome_unknown():
    def adapter(req):
        return make_adapter_response(
            adapter_id=req.adapter_id,request_fingerprint=req.request_fingerprint,
            outcome="SUCCEEDED",external_receipt_id=None,registry=ereg(),
        )
    r=execute(adapter=adapter)
    assert r.outcome=="OUTCOME_UNKNOWN"
    assert r.outcome_unknown is True
    assert r.external_receipt_id is None


def test_adapter_exception_becomes_outcome_unknown():
    def adapter(_):
        raise RuntimeError("network broke after send")
    r=execute(adapter=adapter)
    assert r.outcome=="OUTCOME_UNKNOWN"
    assert r.side_effect_attempted is True
    assert r.outcome_unknown is True


def test_mismatched_adapter_response_becomes_outcome_unknown():
    def adapter(req):
        return make_adapter_response(
            adapter_id="WRONG",request_fingerprint=req.request_fingerprint,
            outcome="SUCCEEDED",external_receipt_id="EXT-X",registry=ereg(),
        )
    r=execute(adapter=adapter)
    assert r.outcome=="OUTCOME_UNKNOWN"
    assert r.external_receipt_id is None


def test_duplicate_success_is_suppressed_without_second_adapter_call():
    first=execute()
    calls={"n":0}
    def adapter(req):
        calls["n"]+=1
        return success_adapter(req)
    second=execute(adapter=adapter,prior=(first,))
    assert second.outcome=="DUPLICATE_SUPPRESSED"
    assert second.side_effect_attempted is False
    assert second.duplicate_suppressed is True
    assert calls["n"]==0


def test_outcome_unknown_is_never_silently_retried():
    def uncertain(_):
        raise RuntimeError("timeout")
    first=execute(adapter=uncertain)
    calls={"n":0}
    def retry(req):
        calls["n"]+=1
        return success_adapter(req)
    second=execute(adapter=retry,prior=(first,))
    assert second.outcome=="BLOCKED_OUTCOME_UNKNOWN"
    assert second.side_effect_attempted is False
    assert second.outcome_unknown is True
    assert calls["n"]==0


def test_failed_receipt_same_idempotency_is_also_not_silently_reexecuted():
    def fail(req):
        return make_adapter_response(
            adapter_id=req.adapter_id,request_fingerprint=req.request_fingerprint,
            outcome="FAILED",external_receipt_id="EXT-F",registry=ereg(),
        )
    first=execute(adapter=fail)
    second=execute(prior=(first,))
    assert second.outcome=="DUPLICATE_SUPPRESSED"
    assert second.side_effect_attempted is False


def test_authority_is_revalidated_immediately_before_execution():
    p=proposal(); a=approval(p)
    auth=authority(end="2026-09-18T09:07:30-07:00")
    aa=authorize_action(
        authorized_action_id="AA-1",proposal=p,approval=a,authority=auth,
        authorized_at="2026-09-18T09:06:00-07:00",registry=ereg(),
    )
    req=request(aa)
    with pytest.raises(ValueError,match="not valid"):
        execute(p=p,a=a,auth=auth,aa=aa,req=req)


def test_request_contains_no_price_terms_seller_approval_or_message_payload():
    req=request()
    names=set(req.__dataclass_fields__)
    assert names.isdisjoint(set(ereg()["prohibited_request_fields"]))


def test_proposal_must_remain_pristine_proposed_state():
    p=proposal()
    bad=p.__class__(**{**p.__dict__,"authorization_state":"AUTHORIZED"})
    with pytest.raises(ValueError,match="authority state is not pristine"):
        authorized(p=bad,a=approval(p),auth=authority())
