import pytest

from src.seller_intelligence.workspace import ReviewItem, SellerIntelligenceCase
from src.listing_execution.action_planning import build_governed_action_proposal, load_action_proposal_registry, make_action_intent, make_listing_context
from src.listing_execution.authorized_execution import (
    authorize_action, build_execution_request, execute_authorized_action, load_execution_registry,
    make_adapter_response, make_execution_authority, make_human_approval,
)
from src.listing_execution.verification_reconciliation import (
    build_reconciliation_case, build_rollback_request, execute_rollback,
    load_verification_registry, make_observed_state_evidence, make_rollback_adapter_response,
    make_rollback_approval, make_rollback_authority, make_verification_request, verify_execution,
)

P="registries/listing_execution/m12-001-action-proposal-v1.0.yaml"
E="registries/listing_execution/m12-002-authorized-execution-v1.0.yaml"
V="registries/listing_execution/m12-003-verification-reconciliation-v1.0.yaml"
M11="8c5c656934909c10c3c5bc52ae9d12b3c646348686f3d1d787a9b0b067ce6ccf"

def preg(): return load_action_proposal_registry(P)
def ereg(): return load_execution_registry(E)
def vreg(): return load_verification_registry(V)

def chain(outcome="SUCCEEDED"):
    c=SellerIntelligenceCase("C","SUB",(),(),(ReviewItem("R","1"*64,"S","PENDING",("X",),None,None,"2"*64),),(),(),"REVIEW_PENDING_ITEM","INTERNAL",False,"NONE","3"*64)
    lc=make_listing_context(listing_id="L",subject_property_id="SUB",listing_status="ACTIVE",freshness_state="CURRENT",observed_at="2026-09-18T09:00:00-07:00",source_fingerprint="4"*64,registry=preg())
    i=make_action_intent(intent_id="I",subject_property_id="SUB",action_type="REFRESH_MARKET_EVIDENCE",origin="SYSTEM_SIGNAL",target_review_item_id="R",requested_at="2026-09-18T09:01:00-07:00",requested_policy_version="LISTING-ACTION-PROPOSAL-v1.0",registry=preg())
    p=build_governed_action_proposal(proposal_id="P",case=c,m11_release_certified=True,m11_release_evidence_fingerprint="5"*64,m11_release_certification_root=M11,listing_context=lc,intent=i,registry=preg())
    a=make_human_approval(approval_id="A",proposal_fingerprint=p.proposal_fingerprint,actor_id="H",decision="APPROVED",approved_at="2026-09-18T09:02:00-07:00",rationale_fingerprint="6"*64,registry=ereg())
    auth=make_execution_authority(authority_id="AUTH",principal_id="H",listing_id="L",allowed_action_types=("REFRESH_MARKET_EVIDENCE",),status="VALID",valid_from="2026-09-18T08:00:00-07:00",valid_until="2026-09-18T12:00:00-07:00",source_fingerprint="7"*64,registry=ereg())
    aa=authorize_action(authorized_action_id="AA",proposal=p,approval=a,authority=auth,authorized_at="2026-09-18T09:03:00-07:00",registry=ereg())
    req=build_execution_request(request_id="REQ",authorized_action=aa,adapter_id="X",requested_at="2026-09-18T09:04:00-07:00")
    def adapter(r):
        ext="EXT" if outcome=="SUCCEEDED" else "EXT-F" if outcome=="FAILED" else None
        return make_adapter_response(adapter_id="X",request_fingerprint=r.request_fingerprint,outcome=outcome,external_receipt_id=ext,registry=ereg())
    receipt=execute_authorized_action(receipt_id="RC",proposal=p,approval=a,authority=auth,authorized_action=aa,request=req,adapter=adapter,prior_receipts=(),execution_at="2026-09-18T09:05:00-07:00",registry=ereg())
    return p,aa,receipt

def observation(code="APPLIED"):
    return make_observed_state_evidence(observation_id="O",listing_id="L",action_type="REFRESH_MARKET_EVIDENCE",observed_at="2026-09-18T09:10:00-07:00",state_code=code,source_fingerprint="8"*64,independent=True)

def verification(receipt=None,obs=None,expected="APPLIED",prior=()):
    if receipt is None: receipt=chain()[2]
    vr=make_verification_request(verification_id="V1",receipt=receipt,listing_id="L",action_type="REFRESH_MARKET_EVIDENCE",requested_at="2026-09-18T09:09:00-07:00")
    return verify_execution(request=vr,receipt=receipt,observation=obs if obs is not None else observation(),expected_state_code=expected,verified_at="2026-09-18T09:11:00-07:00",prior_verifications=prior,registry=vreg())

def test_success_receipt_is_not_self_verifying():
    r=chain()[2]
    v=verification(r,obs=None,expected="APPLIED")
    assert v.verification_state=="VERIFIED"

def test_independent_matching_observation_verifies():
    assert verification().verification_state=="VERIFIED"

def test_mismatch_creates_open_reconciliation_case():
    p,aa,r=chain()
    v=verification(r,obs=observation("NOT_APPLIED"))
    assert v.verification_state=="MISMATCH"
    c=build_reconciliation_case(reconciliation_case_id="REC",receipt=r,verification=v,opened_at="2026-09-18T09:12:00-07:00")
    assert c is not None
    assert c.state=="OPEN"
    assert c.rollback_eligibility=="ELIGIBLE"

def test_outcome_unknown_stays_explicit_and_is_not_rollback_eligible():
    p,aa,r=chain("OUTCOME_UNKNOWN")
    vr=make_verification_request(verification_id="V1",receipt=r,listing_id="L",action_type="REFRESH_MARKET_EVIDENCE",requested_at="2026-09-18T09:09:00-07:00")
    v=verify_execution(request=vr,receipt=r,observation=None,expected_state_code="APPLIED",verified_at="2026-09-18T09:11:00-07:00",prior_verifications=(),registry=vreg())
    assert v.verification_state=="OUTCOME_UNKNOWN"
    c=build_reconciliation_case(reconciliation_case_id="REC",receipt=r,verification=v,opened_at="2026-09-18T09:12:00-07:00")
    assert c.rollback_eligibility=="NOT_ELIGIBLE"

def test_duplicate_suppressed_execution_is_not_applicable():
    p,aa,r=chain()
    dup=r.__class__(**{**r.__dict__,"outcome":"DUPLICATE_SUPPRESSED","side_effect_attempted":False,"duplicate_suppressed":True})
    vr=make_verification_request(verification_id="V1",receipt=dup,listing_id="L",action_type="REFRESH_MARKET_EVIDENCE",requested_at="2026-09-18T09:09:00-07:00")
    v=verify_execution(request=vr,receipt=dup,observation=None,expected_state_code=None,verified_at="2026-09-18T09:11:00-07:00",prior_verifications=(),registry=vreg())
    assert v.verification_state=="NOT_APPLICABLE"

def test_non_independent_observation_rejected():
    with pytest.raises(ValueError,match="independently sourced"):
        make_observed_state_evidence(observation_id="O",listing_id="L",action_type="REFRESH_MARKET_EVIDENCE",observed_at="2026-09-18T09:10:00-07:00",state_code="APPLIED",source_fingerprint="8"*64,independent=False)

def test_same_execution_receipt_cannot_be_verified_twice():
    r=chain()[2]
    first=verification(r)
    vr=make_verification_request(verification_id="V2",receipt=r,listing_id="L",action_type="REFRESH_MARKET_EVIDENCE",requested_at="2026-09-18T09:12:00-07:00")
    with pytest.raises(ValueError,match="already independently verified"):
        verify_execution(request=vr,receipt=r,observation=observation(),expected_state_code="APPLIED",verified_at="2026-09-18T09:13:00-07:00",prior_verifications=(first,),registry=vreg())

def rollback_inputs():
    p,aa,r=chain()
    v=verification(r,obs=observation("NOT_APPLIED"))
    c=build_reconciliation_case(reconciliation_case_id="REC",receipt=r,verification=v,opened_at="2026-09-18T09:12:00-07:00")
    ap=make_rollback_approval(rollback_approval_id="RA",reconciliation_case_fingerprint=c.case_fingerprint,actor_id="H2",decision="APPROVED",approved_at="2026-09-18T09:13:00-07:00",rationale_fingerprint="9"*64)
    auth=make_rollback_authority(rollback_authority_id="R-AUTH",principal_id="H2",listing_id="L",allowed_original_action_types=("REFRESH_MARKET_EVIDENCE",),status="VALID",valid_from="2026-09-18T09:00:00-07:00",valid_until="2026-09-18T12:00:00-07:00",source_fingerprint="a"*64)
    req=build_rollback_request(rollback_request_id="RR",reconciliation_case=c,original_action=aa,original_receipt=r,verification=v,rollback_approval=ap,rollback_authority=auth,adapter_id="RB",requested_at="2026-09-18T09:14:00-07:00")
    return aa,r,v,c,ap,auth,req

def test_rollback_requires_separate_approval():
    aa,r,v,c,ap,auth,req=rollback_inputs()
    bad=make_rollback_approval(rollback_approval_id="BAD",reconciliation_case_fingerprint=c.case_fingerprint,actor_id="H2",decision="REJECTED",approved_at="2026-09-18T09:13:00-07:00",rationale_fingerprint="9"*64)
    with pytest.raises(ValueError,match="explicit rollback approval"):
        build_rollback_request(rollback_request_id="X",reconciliation_case=c,original_action=aa,original_receipt=r,verification=v,rollback_approval=bad,rollback_authority=auth,adapter_id="RB",requested_at="2026-09-18T09:14:00-07:00")

def test_rollback_requires_separate_authority_scope():
    aa,r,v,c,ap,auth,req=rollback_inputs()
    bad=make_rollback_authority(rollback_authority_id="X",principal_id="H2",listing_id="L",allowed_original_action_types=("REVIEW_MARKETING_PLAN",),status="VALID",valid_from="2026-09-18T09:00:00-07:00",valid_until="2026-09-18T12:00:00-07:00",source_fingerprint="b"*64)
    with pytest.raises(ValueError,match="action scope mismatch"):
        build_rollback_request(rollback_request_id="X",reconciliation_case=c,original_action=aa,original_receipt=r,verification=v,rollback_approval=ap,rollback_authority=bad,adapter_id="RB",requested_at="2026-09-18T09:14:00-07:00")

def test_rollback_request_has_exact_original_chain_lineage():
    aa,r,v,c,ap,auth,req=rollback_inputs()
    assert req.original_proposal_fingerprint==aa.proposal_fingerprint
    assert req.original_authorized_action_fingerprint==aa.authorized_action_fingerprint
    assert req.original_execution_receipt_fingerprint==r.receipt_fingerprint
    assert req.verification_fingerprint==v.verification_fingerprint
    assert req.reconciliation_case_fingerprint==c.case_fingerprint

def test_rollback_authority_revalidated_at_execution():
    aa,r,v,c,ap,auth,req=rollback_inputs()
    expired=make_rollback_authority(rollback_authority_id="R-AUTH",principal_id="H2",listing_id="L",allowed_original_action_types=("REFRESH_MARKET_EVIDENCE",),status="VALID",valid_from="2026-09-18T09:00:00-07:00",valid_until="2026-09-18T09:14:30-07:00",source_fingerprint="a"*64)
    req2=build_rollback_request(rollback_request_id="RR2",reconciliation_case=c,original_action=aa,original_receipt=r,verification=v,rollback_approval=ap,rollback_authority=expired,adapter_id="RB",requested_at="2026-09-18T09:14:00-07:00")
    with pytest.raises(ValueError,match="not valid at execution time"):
        execute_rollback(rollback_receipt_id="RRC",request=req2,reconciliation_case=c,rollback_approval=ap,rollback_authority=expired,adapter=lambda _:None,prior_receipts=(),execution_at="2026-09-18T09:15:00-07:00",registry=vreg())

def test_successful_rollback_is_immutable_and_idempotent():
    aa,r,v,c,ap,auth,req=rollback_inputs()
    def adapter(x):
        return make_rollback_adapter_response(adapter_id="RB",request_fingerprint=x.request_fingerprint,outcome="SUCCEEDED",external_receipt_id="RB-EXT",registry=vreg())
    first=execute_rollback(rollback_receipt_id="RRC1",request=req,reconciliation_case=c,rollback_approval=ap,rollback_authority=auth,adapter=adapter,prior_receipts=(),execution_at="2026-09-18T09:15:00-07:00",registry=vreg())
    calls={"n":0}
    def second_adapter(x):
        calls["n"]+=1
        return adapter(x)
    second=execute_rollback(rollback_receipt_id="RRC2",request=req,reconciliation_case=c,rollback_approval=ap,rollback_authority=auth,adapter=second_adapter,prior_receipts=(first,),execution_at="2026-09-18T09:16:00-07:00",registry=vreg())
    assert first.outcome=="SUCCEEDED" and first.immutable is True
    assert second.outcome=="DUPLICATE_SUPPRESSED"
    assert second.side_effect_attempted is False
    assert calls["n"]==0

def test_unknown_rollback_is_not_silently_retried():
    aa,r,v,c,ap,auth,req=rollback_inputs()
    first=execute_rollback(rollback_receipt_id="RRC1",request=req,reconciliation_case=c,rollback_approval=ap,rollback_authority=auth,adapter=lambda _: (_ for _ in ()).throw(RuntimeError()),prior_receipts=(),execution_at="2026-09-18T09:15:00-07:00",registry=vreg())
    second=execute_rollback(rollback_receipt_id="RRC2",request=req,reconciliation_case=c,rollback_approval=ap,rollback_authority=auth,adapter=lambda _:None,prior_receipts=(first,),execution_at="2026-09-18T09:16:00-07:00",registry=vreg())
    assert first.outcome=="OUTCOME_UNKNOWN"
    assert second.outcome=="BLOCKED_OUTCOME_UNKNOWN"
    assert second.side_effect_attempted is False
