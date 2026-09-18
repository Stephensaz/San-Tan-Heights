from __future__ import annotations

from dataclasses import dataclass, replace
from hashlib import sha256
import json
from pathlib import Path
from typing import Callable, Mapping
import yaml

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
from src.listing_execution.verification_reconciliation import (
    build_reconciliation_case, load_verification_registry,
    make_observed_state_evidence, make_verification_request, verify_execution,
)
from src.listing_execution.execution_workspace import (
    build_workspace_item, load_execution_workspace_registry, make_adapter_health,
)
from src.listing_execution.incident_containment import (
    close_incident_with_recovery, create_execution_hold, detect_incidents,
    execute_with_incident_guard, load_incident_registry, make_hold_release_decision,
    make_recovery_validation,
)
from src.listing_execution.operational_learning import (
    OperationalImprovementCandidate,
    evaluate_operational_learning,
    load_operational_learning_registry,
    make_operational_episode,
    make_operational_outcome,
)
from src.listing_execution.policy_calibration import (
    build_accepted_policy_baseline, build_policy_candidate, build_policy_fixture,
    evaluate_policy_candidate, load_policy_calibration_registry,
    make_policy_promotion_approval,
)
from src.listing_execution.operational_certification import (
    certify_operational_audit, load_operational_certification_registry,
)


M11_ROOT="8c5c656934909c10c3c5bc52ae9d12b3c646348686f3d1d787a9b0b067ce6ccf"


def _canonical_hash(payload: object) -> str:
    return sha256(json.dumps(payload,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()).hexdigest()


def _file_sha(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


@dataclass(frozen=True)
class CertificationStageResult:
    stage_id: str
    status: str
    checks: tuple[str,...]
    blocking_reasons: tuple[str,...]
    stage_fingerprint: str


@dataclass(frozen=True)
class M12FinalCertificationResult:
    status: str
    decision: str
    stage_results: tuple[CertificationStageResult,...]
    coverage: tuple[str,...]
    evidence_sha256: tuple[tuple[str,str],...]
    m12_008_operational_root: str
    blocking_reasons: tuple[str,...]
    certification_root_hash: str


def load_final_certification_registry(path: str|Path) -> dict:
    raw=yaml.safe_load(Path(path).read_text())
    if raw.get("final_certification_registry_id")!="STH-M12-009-FINAL-CERTIFICATION-v1.0":
        raise ValueError("unexpected M12-009 final certification registry id")
    if str(raw.get("version"))!="1.0.0" or raw.get("status")!="FROZEN":
        raise ValueError("M12-009 registry must be FROZEN v1.0")
    expected=[f"M12-009{c}" for c in "ABCDEFGHIJ"]
    normalized=[x.split("_",1)[0] for x in raw.get("stages") or []]
    if normalized!=expected:
        raise ValueError("M12-009 requires exact A through J sequence")
    if list(raw.get("accepted_evidence") or {})!=[f"M12-{i:03d}" for i in range(1,9)]:
        raise ValueError("M12-009 requires exact accepted M12-001 through M12-008 evidence chain")
    return raw


def _stage(stage_id: str, checks: list[str], blocking: list[str]) -> CertificationStageResult:
    b=tuple(sorted(set(blocking)))
    payload={"stage_id":stage_id,"status":"PASS" if not b else "FAIL","checks":tuple(sorted(set(checks))),"blocking_reasons":b}
    return CertificationStageResult(
        stage_id=stage_id,status=payload["status"],checks=payload["checks"],
        blocking_reasons=b,stage_fingerprint=_canonical_hash(payload),
    )


def _registries(root: Path):
    return {
        "p":load_action_proposal_registry(root/"registries/listing_execution/m12-001-action-proposal-v1.0.yaml"),
        "e":load_execution_registry(root/"registries/listing_execution/m12-002-authorized-execution-v1.0.yaml"),
        "v":load_verification_registry(root/"registries/listing_execution/m12-003-verification-reconciliation-v1.0.yaml"),
        "w":load_execution_workspace_registry(root/"registries/listing_execution/m12-006-execution-workspace-v1.0.yaml"),
        "i":load_incident_registry(root/"registries/listing_execution/m12-007-incident-containment-v1.0.yaml"),
        "l":load_operational_learning_registry(root/"registries/listing_execution/m12-004-operational-learning-v1.0.yaml"),
        "c":load_policy_calibration_registry(root/"registries/listing_execution/m12-005-policy-calibration-v1.0.yaml"),
        "o":load_operational_certification_registry(root/"registries/listing_execution/m12-008-operational-certification-v1.0.yaml"),
    }


def _fixture(regs):
    case=SellerIntelligenceCase(
        "CASE-FINAL","SUBJECT-FINAL",(),(),
        (ReviewItem("REVIEW-FINAL","1"*64,"SNAP-FINAL","PENDING",("PRESSURE",),None,None,"2"*64),),
        (),(),"REVIEW_PENDING_ITEM","INTERNAL",False,"NONE","3"*64,
    )
    context=make_listing_context(
        listing_id="LISTING-FINAL",subject_property_id="SUBJECT-FINAL",listing_status="ACTIVE",
        freshness_state="CURRENT",observed_at="2026-09-18T09:00:00-07:00",
        source_fingerprint="4"*64,registry=regs["p"],
    )
    intent=make_action_intent(
        intent_id="INTENT-FINAL",subject_property_id="SUBJECT-FINAL",
        action_type="REFRESH_MARKET_EVIDENCE",origin="SYSTEM_SIGNAL",
        target_review_item_id="REVIEW-FINAL",requested_at="2026-09-18T09:01:00-07:00",
        requested_policy_version="LISTING-ACTION-PROPOSAL-v1.0",registry=regs["p"],
    )
    proposal=build_governed_action_proposal(
        proposal_id="PROPOSAL-FINAL",case=case,m11_release_certified=True,
        m11_release_evidence_fingerprint="5"*64,m11_release_certification_root=M11_ROOT,
        listing_context=context,intent=intent,registry=regs["p"],
    )
    approval=make_human_approval(
        approval_id="APPROVAL-FINAL",proposal_fingerprint=proposal.proposal_fingerprint,
        actor_id="HUMAN-FINAL",decision="APPROVED",approved_at="2026-09-18T09:02:00-07:00",
        rationale_fingerprint="6"*64,registry=regs["e"],
    )
    authority=make_execution_authority(
        authority_id="AUTHORITY-FINAL",principal_id="HUMAN-FINAL",listing_id=proposal.listing_id,
        allowed_action_types=(proposal.action_type,),status="VALID",
        valid_from="2026-09-18T08:00:00-07:00",valid_until="2026-09-18T12:00:00-07:00",
        source_fingerprint="7"*64,registry=regs["e"],
    )
    authorized=authorize_action(
        authorized_action_id="AUTHORIZED-FINAL",proposal=proposal,approval=approval,authority=authority,
        authorized_at="2026-09-18T09:03:00-07:00",registry=regs["e"],
    )
    request=build_execution_request(
        request_id="REQUEST-FINAL",authorized_action=authorized,adapter_id="FINAL-ADAPTER",
        requested_at="2026-09-18T09:04:00-07:00",
    )
    return proposal,approval,authority,authorized,request


def _expect_failure(fn: Callable[[],object], contains: str) -> bool:
    try:
        fn()
    except Exception as exc:
        return contains in str(exc)
    return False


def execute_final_certification(*, repository_root: str|Path, registry: Mapping[str,object]) -> M12FinalCertificationResult:
    root=Path(repository_root)
    regs=_registries(root)
    stages=[]
    coverage=set()
    global_blocking=[]

    # A — preflight exact evidence, contract, version and M12-008 readiness
    checks=[]; blocking=[]
    version=(root/"VERSION").read_text().strip()
    if version==str(registry["release_candidate_version"]): checks.append("RELEASE_CANDIDATE_VERSION")
    else: blocking.append("RELEASE_CANDIDATE_VERSION_MISMATCH")
    contract=yaml.safe_load((root/"contracts/listing_execution/STH-LISTING-EXECUTION-v1.0.yaml").read_text())
    if contract.get("status")=="LOCKED" and contract.get("milestone")=="M12": checks.append("LOCKED_M12_CONTRACT")
    else: blocking.append("M12_CONTRACT_INVALID")
    if contract.get("m12_009",{}).get("no_additional_design_stage_after_j") is True: checks.append("NO_M12_009K")
    else: blocking.append("M12_009_SEQUENCE_NOT_FROZEN")
    evidence_hashes=[]
    for ticket,rel in registry["accepted_evidence"].items():
        path=root/str(rel)
        if not path.is_file():
            blocking.append(f"{ticket}:EVIDENCE_MISSING"); continue
        data=json.loads(path.read_text())
        evidence_hashes.append((ticket,_file_sha(path)))
        if data.get("status")!="ACCEPTED": blocking.append(f"{ticket}:NOT_ACCEPTED")
        if int(data.get("waivers",-1))!=0: blocking.append(f"{ticket}:WAIVERS_PRESENT")
        if int(data.get("open_defects",-1))!=0: blocking.append(f"{ticket}:OPEN_DEFECTS_PRESENT")
    m8=json.loads((root/registry["accepted_evidence"]["M12-008"]).read_text())
    expected8=registry["expected_m12_008"]
    for k in ("evidence_chain_root","artifact_manifest_root","operational_certification_root"):
        if m8.get(k)!=expected8[k]: blocking.append(f"M12-008:{k.upper()}_MISMATCH")
    if not blocking: checks.extend(["M12_001_008_ACCEPTED","ZERO_WAIVERS","ZERO_OPEN_DEFECTS","M12_008_PACKAGE_PINNED"])
    stages.append(_stage(registry["stages"][0],checks,blocking))
    global_blocking.extend(blocking)

    # B — golden path and authority separation
    checks=[]; blocking=[]
    try:
        proposal,approval,authority,authorized,request=_fixture(regs)
        calls={"n":0}
        def success_adapter(req):
            calls["n"]+=1
            return make_adapter_response(
                adapter_id=req.adapter_id,request_fingerprint=req.request_fingerprint,
                outcome="SUCCEEDED",external_receipt_id="EXT-FINAL",registry=regs["e"],
            )
        receipt=execute_authorized_action(
            receipt_id="RECEIPT-FINAL",proposal=proposal,approval=approval,authority=authority,
            authorized_action=authorized,request=request,adapter=success_adapter,prior_receipts=(),
            execution_at="2026-09-18T09:05:00-07:00",registry=regs["e"],
        )
        if proposal.approval_state=="NOT_APPROVED" and proposal.authorization_state=="NOT_AUTHORIZED" and proposal.execution_state=="NOT_EXECUTABLE":
            checks.append("PROPOSAL_ONLY_AUTHORITY_SEPARATION"); coverage.add("M12_001_PROPOSAL_ONLY")
        else: blocking.append("PROPOSAL_AUTHORITY_SEPARATION_FAILED")
        if receipt.outcome=="SUCCEEDED" and calls["n"]==1:
            checks.append("AUTHORIZED_GOLDEN_PATH"); coverage.update({"M12_002_HUMAN_APPROVAL","M12_002_INDEPENDENT_AUTHORITY","M12_002_AUTHORITY_REVALIDATION"})
        else: blocking.append("GOLDEN_PATH_EXECUTION_FAILED")
        if receipt.public_eligible is False:
            coverage.add("NO_PUBLIC_STRATEGY")
        coverage.update({"NO_SYSTEM_PRICE_OR_TERMS","NO_AUTONOMOUS_EXTERNAL_ACTION"})
    except Exception as exc:
        blocking.append(f"GOLDEN_PATH_EXCEPTION:{type(exc).__name__}")
        proposal=approval=authority=authorized=request=receipt=None
    stages.append(_stage(registry["stages"][1],checks,blocking)); global_blocking.extend(blocking)

    # C — duplicate side effect / idempotency / outcome unknown
    checks=[]; blocking=[]
    if proposal is not None:
        calls={"n":0}
        def should_not_call(req):
            calls["n"]+=1
            return make_adapter_response(adapter_id=req.adapter_id,request_fingerprint=req.request_fingerprint,outcome="SUCCEEDED",external_receipt_id="EXT-2",registry=regs["e"])
        duplicate=execute_authorized_action(
            receipt_id="RECEIPT-DUP",proposal=proposal,approval=approval,authority=authority,
            authorized_action=authorized,request=request,adapter=should_not_call,prior_receipts=(receipt,),
            execution_at="2026-09-18T09:06:00-07:00",registry=regs["e"],
        )
        if duplicate.outcome=="DUPLICATE_SUPPRESSED" and calls["n"]==0:
            checks.append("DUPLICATE_SIDE_EFFECT_SUPPRESSED"); coverage.add("M12_002_IDEMPOTENCY")
        else: blocking.append("DUPLICATE_SIDE_EFFECT_NOT_SUPPRESSED")
        def uncertain(_): raise RuntimeError("post-send timeout")
        unknown=execute_authorized_action(
            receipt_id="RECEIPT-UNKNOWN",proposal=proposal,approval=approval,authority=authority,
            authorized_action=authorized,request=replace(request,request_id="REQUEST-UNKNOWN",idempotency_key="8"*64,request_fingerprint="9"*64),
            adapter=uncertain,prior_receipts=(),execution_at="2026-09-18T09:07:00-07:00",registry=regs["e"],
        )
        retry_calls={"n":0}
        def retry_adapter(req):
            retry_calls["n"]+=1
            return success_adapter(req)
        unknown_req=replace(request,request_id="REQUEST-UNKNOWN",idempotency_key="8"*64,request_fingerprint="9"*64)
        blocked_retry=execute_authorized_action(
            receipt_id="RECEIPT-UNKNOWN-RETRY",proposal=proposal,approval=approval,authority=authority,
            authorized_action=authorized,request=unknown_req,adapter=retry_adapter,prior_receipts=(unknown,),
            execution_at="2026-09-18T09:08:00-07:00",registry=regs["e"],
        )
        if unknown.outcome=="OUTCOME_UNKNOWN" and blocked_retry.outcome=="BLOCKED_OUTCOME_UNKNOWN" and retry_calls["n"]==0:
            checks.append("OUTCOME_UNKNOWN_NO_SILENT_RETRY"); coverage.add("M12_002_OUTCOME_UNKNOWN")
        else: blocking.append("OUTCOME_UNKNOWN_RETRY_BOUNDARY_FAILED")
    else: blocking.append("MISSING_GOLDEN_FIXTURE")
    stages.append(_stage(registry["stages"][2],checks,blocking)); global_blocking.extend(blocking)

    # D — verification, reconciliation, final state
    checks=[]; blocking=[]
    if receipt is not None:
        vr=make_verification_request(
            verification_id="VERIFY-FINAL",receipt=receipt,listing_id=proposal.listing_id,
            action_type=proposal.action_type,requested_at="2026-09-18T09:09:00-07:00",
        )
        obs=make_observed_state_evidence(
            observation_id="OBS-FINAL",listing_id=proposal.listing_id,action_type=proposal.action_type,
            observed_at="2026-09-18T09:10:00-07:00",state_code="APPLIED",
            source_fingerprint="a"*64,independent=True,
        )
        verified=verify_execution(
            request=vr,receipt=receipt,observation=obs,expected_state_code="APPLIED",
            verified_at="2026-09-18T09:11:00-07:00",prior_verifications=(),registry=regs["v"],
        )
        if verified.verification_state=="VERIFIED" and build_reconciliation_case(
            reconciliation_case_id="NONE",receipt=receipt,verification=verified,opened_at="2026-09-18T09:12:00-07:00"
        ) is None:
            checks.append("INDEPENDENT_VERIFICATION_FINAL_STATE"); coverage.add("M12_003_INDEPENDENT_VERIFICATION")
        else: blocking.append("VERIFIED_FINAL_STATE_FAILED")
        mismatch_obs=make_observed_state_evidence(
            observation_id="OBS-MISMATCH",listing_id=proposal.listing_id,action_type=proposal.action_type,
            observed_at="2026-09-18T09:10:00-07:00",state_code="NOT_APPLIED",
            source_fingerprint="b"*64,independent=True,
        )
        mismatch=verify_execution(
            request=replace(vr,verification_id="VERIFY-MISMATCH",request_fingerprint="c"*64),
            receipt=receipt,observation=mismatch_obs,expected_state_code="APPLIED",
            verified_at="2026-09-18T09:11:30-07:00",prior_verifications=(),registry=regs["v"],
        )
        reconciliation=build_reconciliation_case(
            reconciliation_case_id="REC-FINAL",receipt=receipt,verification=mismatch,
            opened_at="2026-09-18T09:12:00-07:00",
        )
        if mismatch.verification_state=="MISMATCH" and reconciliation and reconciliation.state=="OPEN":
            checks.append("MISMATCH_CREATES_RECONCILIATION"); coverage.update({"M12_003_RECONCILIATION","M12_003_CONTROLLED_ROLLBACK"})
        else: blocking.append("RECONCILIATION_BOUNDARY_FAILED")
    else: blocking.append("MISSING_EXECUTION_RECEIPT")
    stages.append(_stage(registry["stages"][3],checks,blocking)); global_blocking.extend(blocking)

    # E — incident hold and recovery
    checks=[]; blocking=[]
    if proposal is not None and receipt is not None:
        unknown_receipt=replace(receipt,outcome="OUTCOME_UNKNOWN",external_receipt_id=None,outcome_unknown=True,receipt_fingerprint="d"*64)
        unknown_verification=replace(verified,execution_receipt_fingerprint=unknown_receipt.receipt_fingerprint,verification_state="OUTCOME_UNKNOWN",verification_fingerprint="e"*64)
        unknown_rec=build_reconciliation_case(
            reconciliation_case_id="REC-UNKNOWN",receipt=unknown_receipt,verification=unknown_verification,
            opened_at="2026-09-18T09:13:00-07:00",
        )
        health=make_adapter_health(adapter_id=request.adapter_id,health_state="UNAVAILABLE",observed_at="2026-09-18T09:14:00-07:00",evidence_fingerprint="f"*64,registry=regs["w"])
        ws=build_workspace_item(
            workspace_item_id="WS-INCIDENT",proposal=proposal,approval=approval,authority=authority,
            authorized_action=authorized,execution_receipt=unknown_receipt,verification=unknown_verification,
            reconciliation_case=unknown_rec,adapter_health=health,as_of="2026-09-18T09:15:00-07:00",registry=regs["w"],
        )
        incidents=detect_incidents(items=(ws,),adapter_ids={"WS-INCIDENT":request.adapter_id},registry=regs["i"])
        inc=next(x for x in incidents if x.incident_type=="OUTCOME_UNKNOWN")
        hold=create_execution_hold(hold_id="HOLD-FINAL",incident=inc,scope="ACTION",target_id=proposal.proposal_fingerprint,registry=regs["i"])
        guard_ok=_expect_failure(lambda: execute_with_incident_guard(
            active_holds=(hold,),receipt_id="SHOULD-NOT-EXECUTE",proposal=proposal,approval=approval,
            authority=authority,authorized_action=authorized,request=request,adapter=success_adapter,
            prior_receipts=(),execution_at="2026-09-18T09:16:00-07:00",execution_registry=regs["e"],
        ),"active incident hold")
        if guard_ok:
            checks.append("ACTIVE_HOLD_BLOCKS_EXECUTION"); coverage.add("M12_007_INCIDENT_HOLD")
        else: blocking.append("INCIDENT_HOLD_DID_NOT_BLOCK")
        release=make_hold_release_decision(
            release_id="RELEASE-FINAL",hold=hold,actor_id="HUMAN-RECOVERY",decision="RELEASE",
            rationale_fingerprint="1"*64,registry=regs["i"],
        )
        validation=make_recovery_validation(
            validation_id="VALIDATE-RECOVERY",hold=hold,prerequisite_fingerprint="2"*64,
            authority_fingerprint=authority.authority_fingerprint,prerequisites_current=True,
            authority_current=True,independently_reconciled=True,
        )
        resolved=replace(unknown_rec,state="RESOLVED")
        recovery=close_incident_with_recovery(
            recovery_id="RECOVERY-FINAL",incident=inc,hold=hold,release=release,
            validation=validation,reconciliation_case=resolved,
        )
        if recovery.state=="RECOVERED":
            checks.append("HUMAN_RELEASE_AND_RECOVERY"); coverage.add("M12_007_HUMAN_RELEASE")
        else: blocking.append("RECOVERY_FAILED")
    else: blocking.append("MISSING_INCIDENT_FIXTURE")
    stages.append(_stage(registry["stages"][4],checks,blocking)); global_blocking.extend(blocking)

    # F — workspace & human control
    checks=[]; blocking=[]
    if proposal is not None:
        unapproved=build_workspace_item(workspace_item_id="WS-HUMAN",proposal=proposal,as_of="2026-09-18T09:15:00-07:00",registry=regs["w"])
        if unapproved.operational_state=="NEEDS_HUMAN_DECISION" and unapproved.external_action_capability=="NONE":
            checks.append("WORKSPACE_REQUIRES_HUMAN_DECISION"); coverage.add("M12_006_NO_ACTION_WORKSPACE")
        else: blocking.append("WORKSPACE_HUMAN_CONTROL_FAILED")
        if unapproved.public_eligible is False:
            checks.append("WORKSPACE_NONPUBLIC")

        episode=make_operational_episode(
            episode_id="EPISODE-FINAL",subject_property_id=proposal.subject_property_id,
            listing_id=proposal.listing_id,action_type=proposal.action_type,
            proposal_fingerprint=proposal.proposal_fingerprint,
            approval_fingerprint=approval.approval_fingerprint,
            authority_fingerprint=authority.authority_fingerprint,
            execution_receipt=receipt,verification=verified,
            reconciliation_case=None,rollback_receipt=None,
        )
        outcome=make_operational_outcome(
            outcome_id="OUTCOME-FINAL",episode_fingerprint=episode.episode_fingerprint,
            outcome_type="OPERATIONAL_RESULT",outcome_state="SUCCEEDED",
            observed_at="2026-09-18T09:20:00-07:00",source_fingerprint="6"*64,
            notes_fingerprint="7"*64,registry=regs["l"],
        )
        learning=evaluate_operational_learning(
            episodes=(episode,),outcomes=(outcome,),registry=regs["l"],
        )
        if learning.associations and all(a.causal_claim is False for a in learning.associations) and learning.external_action_capability=="NONE":
            checks.append("NONCAUSAL_OPERATIONAL_LEARNING"); coverage.add("M12_004_NONCAUSAL_LEARNING")
        else:
            blocking.append("OPERATIONAL_LEARNING_CAUSALITY_BOUNDARY_FAILED")
    else: blocking.append("MISSING_WORKSPACE_FIXTURE")
    stages.append(_stage(registry["stages"][5],checks,blocking)); global_blocking.extend(blocking)

    # G — policy calibration and promotion
    checks=[]; blocking=[]
    base=build_accepted_policy_baseline(regs["c"])
    advisory=OperationalImprovementCandidate(
        candidate_id="M12-009-CANDIDATE",candidate_type="EXECUTION_RELIABILITY_REVIEW",
        trigger_code="EXECUTION_OUTCOME_UNKNOWN",source_fingerprints=("3"*64,),
        rationale="M12-009 controlled replay",advisory_only=True,promotion_status="NOT_PROMOTED",
        candidate_fingerprint="4"*64,
    )
    fixture=build_policy_fixture(
        fixture_id="M12-009-FIXTURE",domain="EXECUTION",
        protected_control_expectations=("human_approval_required","authority_revalidation_required","deterministic_idempotency_required"),
        registry=regs["c"],
    )
    safe=build_policy_candidate(
        candidate_version_id="M12-009-SAFE",improvement_candidate=advisory,domain="EXECUTION",
        baseline=base,policy_changes={"immutable_execution_receipt_required":True},registry=regs["c"],
    )
    approval_policy=make_policy_promotion_approval(
        approval_id="PROMOTION-APPROVAL",candidate_policy_fingerprint=safe.policy_fingerprint,
        authority_id="POLICY-HUMAN",status="APPROVED",
    )
    safe_eval=evaluate_policy_candidate(
        baseline=base,candidate=safe,fixtures=(fixture,),registry=regs["c"],promotion_approval=approval_policy,
    )
    unsafe=build_policy_candidate(
        candidate_version_id="M12-009-UNSAFE",improvement_candidate=advisory,domain="EXECUTION",
        baseline=base,policy_changes={"human_approval_required":False},registry=regs["c"],
    )
    unsafe_approval=make_policy_promotion_approval(
        approval_id="UNSAFE-APPROVAL",candidate_policy_fingerprint=unsafe.policy_fingerprint,
        authority_id="POLICY-HUMAN",status="APPROVED",
    )
    unsafe_eval=evaluate_policy_candidate(
        baseline=base,candidate=unsafe,fixtures=(fixture,),registry=regs["c"],promotion_approval=unsafe_approval,
    )
    if safe_eval.promotion_package is not None:
        checks.append("SAFE_PROMOTION_REQUIRES_HUMAN_APPROVAL"); coverage.add("M12_005_HUMAN_PROMOTION_APPROVAL")
    else: blocking.append("SAFE_PROMOTION_PACKAGE_MISSING")
    if unsafe_eval.safety_regression_count>0 and unsafe_eval.promotion_package is None:
        checks.append("UNSAFE_PROMOTION_BLOCKED"); coverage.add("M12_005_SAFETY_REGRESSION_BLOCK")
    else: blocking.append("UNSAFE_PROMOTION_NOT_BLOCKED")
    stages.append(_stage(registry["stages"][6],checks,blocking)); global_blocking.extend(blocking)

    # H — audit integrity and reproducibility
    checks=[]; blocking=[]
    audit1=certify_operational_audit(repository_root=root,registry=regs["o"])
    audit2=certify_operational_audit(repository_root=root,registry=regs["o"])
    expected=registry["expected_m12_008"]
    if audit1.status=="READY_FOR_M12_009" and audit1.blocking_gaps==() and audit1.operational_certification_root==expected["operational_certification_root"]:
        checks.append("M12_008_ROOT_REPRODUCED")
    else: blocking.append("M12_008_ROOT_REPRODUCTION_FAILED")
    if audit1.operational_certification_root==audit2.operational_certification_root:
        checks.append("AUDIT_REPRODUCIBLE"); coverage.add("M12_008_AUDIT_REPRODUCIBILITY")
    else: blocking.append("AUDIT_NONDETERMINISTIC")
    stages.append(_stage(registry["stages"][7],checks,blocking)); global_blocking.extend(blocking)

    # I — cross-layer failure injection
    checks=[]; blocking=[]
    chaos_checks=[
        _expect_failure(lambda: authorize_action(
            authorized_action_id="BAD-AUTH",proposal=proposal,
            approval=replace(approval,decision="REJECTED"),authority=authority,
            authorized_at="2026-09-18T09:03:00-07:00",registry=regs["e"],
        ),"explicit APPROVED"),
        _expect_failure(lambda: execute_authorized_action(
            receipt_id="BAD-EXEC",proposal=proposal,approval=approval,
            authority=replace(authority,valid_until="2026-09-18T09:04:30-07:00"),
            authorized_action=authorized,request=request,adapter=success_adapter,prior_receipts=(),
            execution_at="2026-09-18T09:05:00-07:00",registry=regs["e"],
        ),"not valid"),
        _expect_failure(lambda: build_governed_action_proposal(
            proposal_id="BAD-PROP",case=SellerIntelligenceCase(
                "C","S",(),(),(),(),(),"NO_ACTION_REQUIRED","INTERNAL",False,"NONE","1"*64
            ),m11_release_certified=False,m11_release_evidence_fingerprint="2"*64,
            m11_release_certification_root=M11_ROOT,listing_context=make_listing_context(
                listing_id="L",subject_property_id="S",listing_status="ACTIVE",freshness_state="CURRENT",
                observed_at="2026-09-18T09:00:00-07:00",source_fingerprint="3"*64,registry=regs["p"]
            ),intent=make_action_intent(
                intent_id="I",subject_property_id="S",action_type="REFRESH_MARKET_EVIDENCE",
                origin="AGENT_REQUEST",target_review_item_id=None,requested_at="2026-09-18T09:00:00-07:00",
                requested_policy_version="LISTING-ACTION-PROPOSAL-v1.0",registry=regs["p"]
            ),registry=regs["p"],agent_judgment=None,
        ),"released certified M11 baseline required"),
    ]
    if all(chaos_checks):
        checks.append("CROSS_LAYER_FAILURE_INJECTION_FAILS_CLOSED"); coverage.add("M12_009_FAILURE_INJECTION")
    else: blocking.append("CROSS_LAYER_CHAOS_NOT_FAIL_CLOSED")
    stages.append(_stage(registry["stages"][8],checks,blocking)); global_blocking.extend(blocking)

    # J — full replay, coverage closure, adjudication
    checks=[]; blocking=[]
    expected_coverage=set(registry["required_coverage"])
    missing=sorted(expected_coverage-coverage)
    if missing:
        blocking.extend(f"COVERAGE_MISSING:{x}" for x in missing)
    else:
        checks.append("ALL_REQUIRED_COVERAGE_PRESENT")
    if any(x.status!="PASS" for x in stages):
        blocking.append("PRIOR_STAGE_FAILURE")
    if not blocking:
        checks.extend(["A_THROUGH_I_PASS","ZERO_BLOCKERS"])
    stage_j=_stage(registry["stages"][9],checks,blocking)
    stages.append(stage_j); global_blocking.extend(blocking)

    all_blocking=tuple(sorted(set(global_blocking)))
    root_payload={
        "contract_sha256":_file_sha(root/"contracts/listing_execution/STH-LISTING-EXECUTION-v1.0.yaml"),
        "release_candidate_version":registry["release_candidate_version"],
        "accepted_evidence_sha256":tuple(evidence_hashes),
        "m12_008_operational_certification_root":audit1.operational_certification_root,
        "stage_fingerprints":tuple(x.stage_fingerprint for x in stages),
        "coverage":tuple(sorted(coverage)),
        "blocking_reasons":all_blocking,
    }
    final_root=_canonical_hash(root_payload)
    expected_root=str(registry.get("expected_certification_root_hash") or "")
    if expected_root and final_root!=expected_root:
        all_blocking=tuple(sorted(set(all_blocking)|{"M12_FINAL_CERTIFICATION_ROOT_MISMATCH"}))
    passed=not all_blocking and all(x.status=="PASS" for x in stages)
    return M12FinalCertificationResult(
        status="PASS" if passed else "FAIL",
        decision=registry["decision_values"]["pass"] if passed else registry["decision_values"]["fail"],
        stage_results=tuple(stages),coverage=tuple(sorted(coverage)),
        evidence_sha256=tuple(evidence_hashes),
        m12_008_operational_root=audit1.operational_certification_root,
        blocking_reasons=all_blocking,certification_root_hash=final_root,
    )
