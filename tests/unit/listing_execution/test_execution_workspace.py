from dataclasses import fields, replace
import pytest

from src.seller_intelligence.workspace import ReviewItem, SellerIntelligenceCase
from src.listing_execution.action_planning import build_governed_action_proposal, load_action_proposal_registry, make_action_intent, make_listing_context
from src.listing_execution.authorized_execution import (
    authorize_action, build_execution_request, execute_authorized_action, load_execution_registry,
    make_adapter_response, make_execution_authority, make_human_approval,
)
from src.listing_execution.verification_reconciliation import (
    build_reconciliation_case, load_verification_registry, make_observed_state_evidence,
    make_verification_request, verify_execution,
)
from src.listing_execution.execution_workspace import (
    build_execution_workspace, build_workspace_item, load_execution_workspace_registry,
    make_adapter_health,
)

P="registries/listing_execution/m12-001-action-proposal-v1.0.yaml"
E="registries/listing_execution/m12-002-authorized-execution-v1.0.yaml"
V="registries/listing_execution/m12-003-verification-reconciliation-v1.0.yaml"
W="registries/listing_execution/m12-006-execution-workspace-v1.0.yaml"
M11="8c5c656934909c10c3c5bc52ae9d12b3c646348686f3d1d787a9b0b067ce6ccf"
NOW="2026-09-18T10:00:00-07:00"

def preg(): return load_action_proposal_registry(P)
def ereg(): return load_execution_registry(E)
def vreg(): return load_verification_registry(V)
def wreg(): return load_execution_workspace_registry(W)

def proposal():
    c=SellerIntelligenceCase("C","SUB",(),(),(ReviewItem("R","1"*64,"S","PENDING",("X",),None,None,"2"*64),),(),(),"REVIEW_PENDING_ITEM","INTERNAL",False,"NONE","3"*64)
    lc=make_listing_context(listing_id="L",subject_property_id="SUB",listing_status="ACTIVE",freshness_state="CURRENT",observed_at="2026-09-18T09:00:00-07:00",source_fingerprint="4"*64,registry=preg())
    i=make_action_intent(intent_id="I",subject_property_id="SUB",action_type="REFRESH_MARKET_EVIDENCE",origin="SYSTEM_SIGNAL",target_review_item_id="R",requested_at="2026-09-18T09:01:00-07:00",requested_policy_version="LISTING-ACTION-PROPOSAL-v1.0",registry=preg())
    return build_governed_action_proposal(proposal_id="P",case=c,m11_release_certified=True,m11_release_evidence_fingerprint="5"*64,m11_release_certification_root=M11,listing_context=lc,intent=i,registry=preg())

def approval(p=None,when="2026-09-18T09:02:00-07:00"):
    p=p or proposal()
    return make_human_approval(approval_id="A",proposal_fingerprint=p.proposal_fingerprint,actor_id="H",decision="APPROVED",approved_at=when,rationale_fingerprint="6"*64,registry=ereg())

def authority(end="2026-09-18T12:00:00-07:00"):
    return make_execution_authority(authority_id="AUTH",principal_id="H",listing_id="L",allowed_action_types=("REFRESH_MARKET_EVIDENCE",),status="VALID",valid_from="2026-09-18T08:00:00-07:00",valid_until=end,source_fingerprint="7"*64,registry=ereg())

def chain(execution_outcome="SUCCEEDED",verification_state="VERIFIED"):
    p=proposal(); a=approval(p); auth=authority()
    aa=authorize_action(authorized_action_id="AA",proposal=p,approval=a,authority=auth,authorized_at="2026-09-18T09:03:00-07:00",registry=ereg())
    req=build_execution_request(request_id="REQ",authorized_action=aa,adapter_id="AD",requested_at="2026-09-18T09:04:00-07:00")
    def adapter(r):
        ext="EXT" if execution_outcome=="SUCCEEDED" else None
        return make_adapter_response(adapter_id="AD",request_fingerprint=r.request_fingerprint,outcome=execution_outcome,external_receipt_id=ext,registry=ereg())
    rc=execute_authorized_action(receipt_id="RC",proposal=p,approval=a,authority=auth,authorized_action=aa,request=req,adapter=adapter,prior_receipts=(),execution_at="2026-09-18T09:05:00-07:00",registry=ereg())
    vrq=make_verification_request(verification_id="V",receipt=rc,listing_id="L",action_type=p.action_type,requested_at="2026-09-18T09:06:00-07:00")
    obs=make_observed_state_evidence(observation_id="O",listing_id="L",action_type=p.action_type,observed_at="2026-09-18T09:07:00-07:00",state_code="APPLIED" if verification_state=="VERIFIED" else "NOT_APPLIED",source_fingerprint="8"*64,independent=True)
    v=verify_execution(request=vrq,receipt=rc,observation=obs,expected_state_code="APPLIED",verified_at="2026-09-18T09:08:00-07:00",prior_verifications=(),registry=vreg())
    rec=build_reconciliation_case(reconciliation_case_id="REC",receipt=rc,verification=v,opened_at="2026-09-18T09:09:00-07:00")
    return p,a,auth,aa,rc,v,rec

def health(state="HEALTHY"):
    return make_adapter_health(adapter_id="AD",health_state=state,observed_at=NOW,evidence_fingerprint="9"*64,registry=wreg())

def test_unapproved_proposal_needs_human_decision():
    p=proposal()
    item=build_workspace_item(workspace_item_id="I1",proposal=p,as_of=NOW,registry=wreg())
    assert item.operational_state=="NEEDS_HUMAN_DECISION"
    assert item.next_safe_action=="REVIEW_AND_DECIDE"

def test_approved_not_executed_is_visible_without_execution_authority():
    p=proposal(); a=approval(p); auth=authority()
    item=build_workspace_item(workspace_item_id="I1",proposal=p,approval=a,authority=auth,as_of=NOW,registry=wreg())
    assert item.operational_state=="APPROVED_NOT_EXECUTED"
    assert item.external_action_capability=="NONE"

def test_expired_authority_is_explicit_and_blocked():
    p=proposal(); a=approval(p); auth=authority(end="2026-09-18T09:30:00-07:00")
    item=build_workspace_item(workspace_item_id="I1",proposal=p,approval=a,authority=auth,as_of=NOW,registry=wreg())
    assert item.operational_state=="BLOCKED"
    assert item.authority_expired is True
    assert "AUTHORITY_EXPIRED" in item.blocking_reasons

def test_stale_approval_is_explicit_and_blocked():
    p=proposal(); a=approval(p,when="2026-09-16T09:00:00-07:00"); auth=authority()
    item=build_workspace_item(workspace_item_id="I1",proposal=p,approval=a,authority=auth,as_of=NOW,registry=wreg(),approval_stale_after_minutes=1440)
    assert item.operational_state=="BLOCKED"
    assert item.approval_stale is True
    assert "STALE_APPROVAL" in item.blocking_reasons

def test_success_plus_verified_is_complete():
    p,a,auth,aa,rc,v,rec=chain()
    item=build_workspace_item(workspace_item_id="I1",proposal=p,approval=a,authority=auth,authorized_action=aa,execution_receipt=rc,verification=v,adapter_health=health(),as_of=NOW,registry=wreg())
    assert item.operational_state=="COMPLETE"
    assert item.verification_state=="VERIFIED"
    assert item.historical_receipt_fingerprints==(rc.receipt_fingerprint,)

def test_execution_without_verification_requires_verification():
    p,a,auth,aa,rc,v,rec=chain()
    item=build_workspace_item(workspace_item_id="I1",proposal=p,approval=a,authority=auth,authorized_action=aa,execution_receipt=rc,adapter_health=health(),as_of=NOW,registry=wreg())
    assert item.operational_state=="VERIFICATION_RECONCILIATION_REQUIRED"
    assert item.next_safe_action=="REVIEW_VERIFICATION_OR_RECONCILIATION"

def test_mismatch_reconciliation_is_visible_and_rollback_eligibility_not_authorization():
    p,a,auth,aa,rc,v,rec=chain(verification_state="MISMATCH")
    item=build_workspace_item(workspace_item_id="I1",proposal=p,approval=a,authority=auth,authorized_action=aa,execution_receipt=rc,verification=v,reconciliation_case=rec,adapter_health=health(),as_of=NOW,registry=wreg())
    assert item.operational_state=="VERIFICATION_RECONCILIATION_REQUIRED"
    assert item.rollback_eligibility=="ELIGIBLE"
    assert item.rollback_authorized is False
    assert "OPEN_RECONCILIATION" in item.blocking_reasons

def test_outcome_unknown_is_blocked_and_explicit():
    p,a,auth,aa,rc,v,rec=chain(execution_outcome="OUTCOME_UNKNOWN",verification_state="MISMATCH")
    item=build_workspace_item(workspace_item_id="I1",proposal=p,approval=a,authority=auth,authorized_action=aa,execution_receipt=rc,verification=v,reconciliation_case=rec,adapter_health=health(),as_of=NOW,registry=wreg())
    assert "OUTCOME_UNKNOWN" in item.blocking_reasons

def test_unavailable_adapter_blocks_not_yet_executed_work():
    p=proposal(); a=approval(p); auth=authority()
    item=build_workspace_item(workspace_item_id="I1",proposal=p,approval=a,authority=auth,adapter_health=health("UNAVAILABLE"),as_of=NOW,registry=wreg())
    assert item.operational_state=="BLOCKED"
    assert "ADAPTER_UNAVAILABLE" in item.blocking_reasons

def test_workspace_is_deterministic_and_counts_exactly_one_state_per_item():
    a=build_workspace_item(workspace_item_id="A",proposal=proposal(),as_of=NOW,registry=wreg())
    p=proposal(); ap=approval(p); auth=authority()
    b=build_workspace_item(workspace_item_id="B",proposal=p,approval=ap,authority=auth,as_of=NOW,registry=wreg())
    x=build_execution_workspace(as_of=NOW,items=[b,a],registry=wreg())
    y=build_execution_workspace(as_of=NOW,items=[a,b],registry=wreg())
    assert x.workspace_fingerprint==y.workspace_fingerprint
    assert sum(n for _,n in x.state_counts)==2

def test_workspace_surfaces_blocked_unknown_and_rollback_eligible_sets():
    p,a,auth,aa,rc,v,rec=chain(verification_state="MISMATCH")
    mismatch=build_workspace_item(workspace_item_id="M",proposal=p,approval=a,authority=auth,authorized_action=aa,execution_receipt=rc,verification=v,reconciliation_case=rec,as_of=NOW,registry=wreg())
    blocked=build_workspace_item(workspace_item_id="B",proposal=proposal(),approval=approval(),authority=authority(end="2026-09-18T09:30:00-07:00"),as_of=NOW,registry=wreg())
    ws=build_execution_workspace(as_of=NOW,items=[mismatch,blocked],registry=wreg())
    assert "B" in ws.blocked_item_ids
    assert "M" in ws.rollback_eligible_item_ids

def test_upstream_lineage_mismatch_fails_closed():
    p=proposal(); a=approval(p); auth=authority()
    bad=replace(a,proposal_fingerprint="f"*64)
    with pytest.raises(ValueError,match="approval/proposal lineage mismatch"):
        build_workspace_item(workspace_item_id="I",proposal=p,approval=bad,authority=auth,as_of=NOW,registry=wreg())

def test_adapter_health_must_match_execution_adapter():
    p,a,auth,aa,rc,v,rec=chain()
    bad=make_adapter_health(adapter_id="OTHER",health_state="HEALTHY",observed_at=NOW,evidence_fingerprint="9"*64,registry=wreg())
    with pytest.raises(ValueError,match="adapter mismatch"):
        build_workspace_item(workspace_item_id="I",proposal=p,approval=a,authority=auth,authorized_action=aa,execution_receipt=rc,verification=v,adapter_health=bad,as_of=NOW,registry=wreg())

def test_workspace_dto_has_no_action_or_price_terms_fields():
    names={x.name for x in fields(type(build_workspace_item(workspace_item_id="I",proposal=proposal(),as_of=NOW,registry=wreg())))}
    assert names.isdisjoint(set(wreg()["prohibited_output_fields"]))

def test_workspace_is_nonpublic_and_no_external_action_capability():
    item=build_workspace_item(workspace_item_id="I",proposal=proposal(),as_of=NOW,registry=wreg())
    ws=build_execution_workspace(as_of=NOW,items=[item],registry=wreg())
    assert item.public_eligible is False and item.external_action_capability=="NONE"
    assert ws.public_eligible is False and ws.external_action_capability=="NONE"
