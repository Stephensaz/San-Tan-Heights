from dataclasses import replace
import pytest

from src.listing_execution.incident_containment import (
    ExecutionHold, OperationalIncident, close_incident_with_recovery, create_execution_hold, detect_incidents,
    execute_with_incident_guard, load_incident_registry, make_hold_release_decision,
    make_recovery_validation,
)
from src.listing_execution.execution_workspace import ExecutionWorkspaceItem
from src.listing_execution.authorized_execution import (
    AuthorizedAction, ExecutionAuthority, ExecutionRequest, HumanApproval,
)

R="registries/listing_execution/m12-007-incident-containment-v1.0.yaml"
def reg(): return load_incident_registry(R)

def item(i="I1",reasons=("OUTCOME_UNKNOWN",),health="HEALTHY",authority_status="VALID",expired=False):
    return ExecutionWorkspaceItem(
        workspace_item_id=i,subject_property_id="S",listing_id="L"+i,proposal_id="P",
        proposal_fingerprint=("a" if i=="I1" else "b")*64,action_type="REFRESH_MARKET_EVIDENCE",
        operational_state="BLOCKED",next_safe_action="REVIEW_BLOCKING_CONDITION",
        blocking_reasons=reasons,approval_status="APPROVED",approval_stale=False,
        authority_status=authority_status,authority_expired=expired,execution_outcome="OUTCOME_UNKNOWN",
        verification_state="OUTCOME_UNKNOWN",reconciliation_state="OPEN",
        rollback_eligibility="NOT_ELIGIBLE",rollback_authorized=False,
        adapter_health_state=health,historical_receipt_fingerprints=("c"*64,),
        lineage_fingerprints=("d"*64,),public_eligible=False,external_action_capability="NONE",
        item_fingerprint=("e" if i=="I1" else "f")*64,
    )

def test_detects_outcome_unknown_and_adapter_incidents_deterministically():
    x=detect_incidents(items=[item(health="UNAVAILABLE")],adapter_ids={"I1":"AD"},registry=reg())
    assert [i.incident_type for i in x]==["ADAPTER_UNAVAILABLE","OUTCOME_UNKNOWN"]
    assert x==detect_incidents(items=[item(health="UNAVAILABLE")],adapter_ids={"I1":"AD"},registry=reg())

def test_repeated_unknown_creates_portfolio_incident():
    x=detect_incidents(items=[item("I1"),item("I2")],adapter_ids={},registry=reg())
    assert any(i.incident_type=="REPEATED_OUTCOME_UNKNOWN" for i in x)

def test_hold_scope_must_be_inside_blast_radius():
    inc=detect_incidents(items=[item()],adapter_ids={"I1":"AD"},registry=reg())[0]
    with pytest.raises(ValueError,match="outside incident blast radius"):
        create_execution_hold(hold_id="H",incident=inc,scope="LISTING",target_id="OTHER",registry=reg())

def test_human_release_and_fresh_revalidation_required():
    inc=[x for x in detect_incidents(items=[item()],adapter_ids={},registry=reg()) if x.incident_type=="OUTCOME_UNKNOWN"][0]
    hold=create_execution_hold(hold_id="H",incident=inc,scope="ACTION",target_id=item().proposal_fingerprint,registry=reg())
    keep=make_hold_release_decision(release_id="R",hold=hold,actor_id="HUMAN",decision="KEEP_HOLD",rationale_fingerprint="1"*64,registry=reg())
    val=make_recovery_validation(validation_id="V",hold=hold,prerequisite_fingerprint="2"*64,authority_fingerprint="3"*64,prerequisites_current=True,authority_current=True,independently_reconciled=True)
    with pytest.raises(ValueError,match="RELEASE"):
        close_incident_with_recovery(recovery_id="REC",incident=inc,hold=hold,release=keep,validation=val,reconciliation_case=None)

def test_outcome_unknown_cannot_close_without_independent_reconciliation():
    inc=[x for x in detect_incidents(items=[item()],adapter_ids={},registry=reg()) if x.incident_type=="OUTCOME_UNKNOWN"][0]
    hold=create_execution_hold(hold_id="H",incident=inc,scope="ACTION",target_id=item().proposal_fingerprint,registry=reg())
    rel=make_hold_release_decision(release_id="R",hold=hold,actor_id="HUMAN",decision="RELEASE",rationale_fingerprint="1"*64,registry=reg())
    val=make_recovery_validation(validation_id="V",hold=hold,prerequisite_fingerprint="2"*64,authority_fingerprint="3"*64,prerequisites_current=True,authority_current=True,independently_reconciled=False)
    with pytest.raises(ValueError,match="independent reconciliation"):
        close_incident_with_recovery(recovery_id="REC",incident=inc,hold=hold,release=rel,validation=val,reconciliation_case=None)

def test_fresh_prerequisite_and_authority_revalidation_required():
    inc=[x for x in detect_incidents(items=[item(reasons=("AUTHORITY_EXPIRED",),authority_status="VALID",expired=True)],adapter_ids={},registry=reg()) if x.incident_type=="AUTHORITY_ANOMALY"][0]
    hold=create_execution_hold(hold_id="H",incident=inc,scope="LISTING",target_id=item(reasons=("AUTHORITY_EXPIRED",),expired=True).listing_id,registry=reg())
    rel=make_hold_release_decision(release_id="R",hold=hold,actor_id="H",decision="RELEASE",rationale_fingerprint="1"*64,registry=reg())
    bad=make_recovery_validation(validation_id="V",hold=hold,prerequisite_fingerprint="2"*64,authority_fingerprint="3"*64,prerequisites_current=False,authority_current=True,independently_reconciled=True)
    with pytest.raises(ValueError,match="fresh prerequisite"):
        close_incident_with_recovery(recovery_id="REC",incident=inc,hold=hold,release=rel,validation=bad,reconciliation_case=None)

def test_active_hold_blocks_governed_execution_before_adapter():
    from src.listing_execution.action_planning import GovernedActionProposal
    from src.listing_execution.authorized_execution import ExecutionReceipt
    p=GovernedActionProposal(
        proposal_id="P",subject_property_id="S",listing_id="L",action_type="REFRESH_MARKET_EVIDENCE",
        origin="SYSTEM_SIGNAL",target_review_item_id=None,reason_codes=(),prerequisites=(),limitations=(),
        source_case_fingerprint="1"*64,listing_context_fingerprint="2"*64,intent_fingerprint="3"*64,
        agent_judgment_fingerprint=None,m11_release_evidence_fingerprint="4"*64,
        m11_release_certification_root="5"*64,policy_version="v",policy_fingerprint="6"*64,
        lineage_fingerprints=(),proposal_status="PROPOSED",approval_state="NOT_APPROVED",
        authorization_state="NOT_AUTHORIZED",schedule_state="NOT_SCHEDULED",queue_state="NOT_QUEUED",
        execution_state="NOT_EXECUTABLE",publication_state="NOT_PUBLISHED",transmission_state="NOT_TRANSMITTED",
        requires_human_approval=True,public_eligible=False,external_action_capability="NONE",
        proposal_fingerprint="a"*64,
    )
    approval=HumanApproval("A",p.proposal_fingerprint,"H","APPROVED","2026-09-18T09:00:00-07:00","7"*64,"8"*64)
    auth=ExecutionAuthority("AUTH","H","L",("REFRESH_MARKET_EVIDENCE",),"VALID","2026-09-18T08:00:00-07:00","2026-09-18T12:00:00-07:00","9"*64,"b"*64)
    aa=AuthorizedAction("AA","P",p.proposal_fingerprint,"L","S",p.action_type,"A",approval.approval_fingerprint,"AUTH",auth.authority_fingerprint,"AUTHORIZED","READY_FOR_EXECUTION","2026-09-18T09:01:00-07:00",(),False,"c"*64)
    req=ExecutionRequest("REQ",aa.authorized_action_fingerprint,p.proposal_fingerprint,"L",p.action_type,"AD","2026-09-18T09:02:00-07:00","d"*64,"e"*64)
    inc=OperationalIncident("INC","ADAPTER_UNAVAILABLE","OPEN","I","L",p.proposal_fingerprint,p.action_type,"AD",("f"*64,),("ADAPTER:AD",),"1"*64)
    hold=ExecutionHold("HOLD",inc.incident_fingerprint,"ADAPTER","AD","ACTIVE","ADAPTER_UNAVAILABLE",(inc.incident_fingerprint,),"2"*64)
    calls={"n":0}
    def adapter(_):
        calls["n"]+=1
        raise AssertionError("must not run")
    with pytest.raises(ValueError,match="active incident hold"):
        execute_with_incident_guard(active_holds=[hold],receipt_id="RC",proposal=p,approval=approval,authority=auth,authorized_action=aa,request=req,adapter=adapter,prior_receipts=(),execution_at="2026-09-18T09:03:00-07:00",execution_registry={"approval":{"required_for_authorization":"APPROVED"},"authority":{"required_status":"VALID"}})
    assert calls["n"]==0
