from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from hashlib import sha256
import json
from pathlib import Path
from typing import Iterable, Mapping
import yaml

from src.listing_execution.action_planning import GovernedActionProposal
from src.listing_execution.authorized_execution import (
    AuthorizedAction,
    ExecutionAuthority,
    ExecutionReceipt,
    HumanApproval,
)
from src.listing_execution.verification_reconciliation import (
    ReconciliationCase,
    RollbackReceipt,
    VerificationReceipt,
)


def _hash(payload: object) -> str:
    raw=json.dumps(payload,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode("utf-8")
    return sha256(raw).hexdigest()


def _parse_ts(value: str, label: str) -> datetime:
    try:
        dt=datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{label} must be ISO-8601") from exc
    if dt.tzinfo is None:
        raise ValueError(f"{label} must include timezone")
    return dt


@dataclass(frozen=True)
class AdapterHealth:
    adapter_id: str
    health_state: str
    observed_at: str
    evidence_fingerprint: str
    health_fingerprint: str


@dataclass(frozen=True)
class ExecutionWorkspaceItem:
    workspace_item_id: str
    subject_property_id: str
    listing_id: str
    proposal_id: str
    proposal_fingerprint: str
    action_type: str
    operational_state: str
    next_safe_action: str
    blocking_reasons: tuple[str,...]
    approval_status: str
    approval_stale: bool
    authority_status: str
    authority_expired: bool
    execution_outcome: str
    verification_state: str
    reconciliation_state: str
    rollback_eligibility: str
    rollback_authorized: bool
    adapter_health_state: str
    historical_receipt_fingerprints: tuple[str,...]
    lineage_fingerprints: tuple[str,...]
    public_eligible: bool
    external_action_capability: str
    item_fingerprint: str


@dataclass(frozen=True)
class ListingExecutionWorkspace:
    as_of: str
    items: tuple[ExecutionWorkspaceItem,...]
    state_counts: tuple[tuple[str,int],...]
    blocked_item_ids: tuple[str,...]
    outcome_unknown_item_ids: tuple[str,...]
    rollback_eligible_item_ids: tuple[str,...]
    public_eligible: bool
    external_action_capability: str
    workspace_fingerprint: str


def load_execution_workspace_registry(path: str|Path) -> dict:
    raw=yaml.safe_load(Path(path).read_text())
    if raw.get("execution_workspace_registry_id")!="STH-M12-006-EXECUTION-WORKSPACE-v1.0":
        raise ValueError("unexpected M12-006 workspace registry id")
    if str(raw.get("version"))!="1.0.0" or raw.get("status")!="FROZEN":
        raise ValueError("M12-006 registry must be FROZEN v1.0")
    if raw.get("ticket")!="M12-006" or raw.get("parent_ticket")!="M12-005":
        raise ValueError("M12-006 registry lineage mismatch")
    return raw


def make_adapter_health(
    *,
    adapter_id: str,
    health_state: str,
    observed_at: str,
    evidence_fingerprint: str,
    registry: Mapping[str,object],
) -> AdapterHealth:
    if not adapter_id.strip():
        raise ValueError("adapter_id required")
    if health_state not in set(registry["adapter_health_states"]):
        raise ValueError("unsupported adapter health state")
    _parse_ts(observed_at,"adapter health observed_at")
    if len(evidence_fingerprint)!=64:
        raise ValueError("adapter health evidence fingerprint must be sha256")
    payload={
        "adapter_id":adapter_id,
        "health_state":health_state,
        "observed_at":observed_at,
        "evidence_fingerprint":evidence_fingerprint,
    }
    return AdapterHealth(**payload,health_fingerprint=_hash(payload))


def _validate_chain(
    proposal: GovernedActionProposal,
    approval: HumanApproval | None,
    authority: ExecutionAuthority | None,
    authorized_action: AuthorizedAction | None,
    execution_receipt: ExecutionReceipt | None,
    verification: VerificationReceipt | None,
    reconciliation_case: ReconciliationCase | None,
    rollback_receipt: RollbackReceipt | None,
) -> None:
    if proposal.public_eligible is not False or proposal.external_action_capability!="NONE":
        raise ValueError("proposal workspace boundary violated")
    if approval is not None and approval.proposal_fingerprint!=proposal.proposal_fingerprint:
        raise ValueError("approval/proposal lineage mismatch")
    if authority is not None and authority.listing_id!=proposal.listing_id:
        raise ValueError("authority/listing lineage mismatch")
    if authorized_action is not None:
        if approval is None or authority is None:
            raise ValueError("authorized action requires approval and authority")
        if authorized_action.proposal_fingerprint!=proposal.proposal_fingerprint:
            raise ValueError("authorized action/proposal lineage mismatch")
        if authorized_action.approval_fingerprint!=approval.approval_fingerprint:
            raise ValueError("authorized action/approval lineage mismatch")
        if authorized_action.authority_fingerprint!=authority.authority_fingerprint:
            raise ValueError("authorized action/authority lineage mismatch")
    if execution_receipt is not None:
        if authorized_action is None:
            raise ValueError("execution receipt requires authorized action")
        if execution_receipt.proposal_fingerprint!=proposal.proposal_fingerprint:
            raise ValueError("execution receipt/proposal lineage mismatch")
        if execution_receipt.authorized_action_fingerprint!=authorized_action.authorized_action_fingerprint:
            raise ValueError("execution receipt/authorized action lineage mismatch")
    if verification is not None:
        if execution_receipt is None:
            raise ValueError("verification requires execution receipt")
        if verification.execution_receipt_fingerprint!=execution_receipt.receipt_fingerprint:
            raise ValueError("verification/execution receipt lineage mismatch")
    if reconciliation_case is not None:
        if verification is None or execution_receipt is None:
            raise ValueError("reconciliation requires verification and execution receipt")
        if reconciliation_case.execution_receipt_fingerprint!=execution_receipt.receipt_fingerprint:
            raise ValueError("reconciliation/execution receipt lineage mismatch")
        if reconciliation_case.verification_fingerprint!=verification.verification_fingerprint:
            raise ValueError("reconciliation/verification lineage mismatch")
    if rollback_receipt is not None:
        if reconciliation_case is None or verification is None or execution_receipt is None:
            raise ValueError("rollback receipt requires reconciliation chain")
        if rollback_receipt.reconciliation_case_fingerprint!=reconciliation_case.case_fingerprint:
            raise ValueError("rollback/reconciliation lineage mismatch")
        if rollback_receipt.original_execution_receipt_fingerprint!=execution_receipt.receipt_fingerprint:
            raise ValueError("rollback/execution lineage mismatch")
        if rollback_receipt.verification_fingerprint!=verification.verification_fingerprint:
            raise ValueError("rollback/verification lineage mismatch")


def build_workspace_item(
    *,
    workspace_item_id: str,
    proposal: GovernedActionProposal,
    as_of: str,
    registry: Mapping[str,object],
    approval: HumanApproval | None = None,
    authority: ExecutionAuthority | None = None,
    authorized_action: AuthorizedAction | None = None,
    execution_receipt: ExecutionReceipt | None = None,
    verification: VerificationReceipt | None = None,
    reconciliation_case: ReconciliationCase | None = None,
    rollback_receipt: RollbackReceipt | None = None,
    adapter_health: AdapterHealth | None = None,
    approval_stale_after_minutes: int = 1440,
) -> ExecutionWorkspaceItem:
    if not workspace_item_id.strip():
        raise ValueError("workspace_item_id required")
    now=_parse_ts(as_of,"workspace as_of")
    _validate_chain(proposal,approval,authority,authorized_action,execution_receipt,verification,reconciliation_case,rollback_receipt)

    blocking=[]
    approval_status="MISSING"
    approval_stale=False
    if approval is not None:
        approval_status=approval.decision
        approved_at=_parse_ts(approval.approved_at,"approval approved_at")
        approval_stale=(now-approved_at).total_seconds()>approval_stale_after_minutes*60
        if approval_stale:
            blocking.append("STALE_APPROVAL")
        if approval.decision!="APPROVED":
            blocking.append("APPROVAL_NOT_APPROVED")

    authority_status="MISSING"
    authority_expired=False
    if authority is not None:
        authority_status=authority.status
        end=_parse_ts(authority.valid_until,"authority valid_until")
        authority_expired=now>end
        if authority.status!="VALID":
            blocking.append("AUTHORITY_NOT_VALID")
        if authority_expired:
            blocking.append("AUTHORITY_EXPIRED")

    execution_outcome=execution_receipt.outcome if execution_receipt else "NOT_EXECUTED"
    verification_state=verification.verification_state if verification else "NOT_VERIFIED"
    reconciliation_state=reconciliation_case.state if reconciliation_case else "NONE"
    rollback_eligibility=reconciliation_case.rollback_eligibility if reconciliation_case else "NOT_ELIGIBLE"
    rollback_authorized=False

    adapter_state=adapter_health.health_state if adapter_health else "UNKNOWN"
    if adapter_health is not None and execution_receipt is not None and adapter_health.adapter_id!=execution_receipt.adapter_id:
        raise ValueError("adapter health/execution receipt adapter mismatch")
    if adapter_state in {"DEGRADED","UNAVAILABLE"} and execution_receipt is None:
        blocking.append("ADAPTER_"+adapter_state)

    outcome_unknown=(execution_receipt is not None and execution_receipt.outcome_unknown) or (verification is not None and verification.verification_state=="OUTCOME_UNKNOWN") or (rollback_receipt is not None and rollback_receipt.outcome_unknown)
    if outcome_unknown:
        blocking.append("OUTCOME_UNKNOWN")

    if reconciliation_case is not None and reconciliation_case.state=="OPEN":
        blocking.append("OPEN_RECONCILIATION")

    if rollback_receipt is not None:
        state="COMPLETE" if rollback_receipt.outcome=="SUCCEEDED" else "BLOCKED" if rollback_receipt.outcome_unknown else "VERIFICATION_RECONCILIATION_REQUIRED"
    elif reconciliation_case is not None or (verification is not None and verification.verification_state in {"MISMATCH","OUTCOME_UNKNOWN"}):
        state="VERIFICATION_RECONCILIATION_REQUIRED"
    elif execution_receipt is not None:
        if execution_receipt.outcome=="SUCCEEDED" and verification is not None and verification.verification_state=="VERIFIED":
            state="COMPLETE"
        elif execution_receipt.outcome_unknown:
            state="BLOCKED"
        elif verification is None:
            state="VERIFICATION_RECONCILIATION_REQUIRED"
        else:
            state="VERIFICATION_RECONCILIATION_REQUIRED"
    elif authorized_action is not None:
        state="BLOCKED" if blocking else "APPROVED_NOT_EXECUTED"
    elif approval is not None and approval.decision=="APPROVED":
        state="BLOCKED" if blocking else "APPROVED_NOT_EXECUTED"
    else:
        state="NEEDS_HUMAN_DECISION"

    if state not in set(registry["operational_states"]):
        raise ValueError("workspace produced unsupported operational state")

    receipts=[]
    if execution_receipt is not None:
        receipts.append(execution_receipt.receipt_fingerprint)
    if rollback_receipt is not None:
        receipts.append(rollback_receipt.receipt_fingerprint)

    lineage={
        proposal.proposal_fingerprint,
        proposal.source_case_fingerprint,
        proposal.m11_release_certification_root,
        proposal.policy_fingerprint,
    }
    for obj,attr in (
        (approval,"approval_fingerprint"),
        (authority,"authority_fingerprint"),
        (authorized_action,"authorized_action_fingerprint"),
        (execution_receipt,"receipt_fingerprint"),
        (verification,"verification_fingerprint"),
        (reconciliation_case,"case_fingerprint"),
        (rollback_receipt,"receipt_fingerprint"),
        (adapter_health,"health_fingerprint"),
    ):
        if obj is not None:
            lineage.add(getattr(obj,attr))

    payload={
        "workspace_item_id":workspace_item_id,
        "subject_property_id":proposal.subject_property_id,
        "listing_id":proposal.listing_id,
        "proposal_id":proposal.proposal_id,
        "proposal_fingerprint":proposal.proposal_fingerprint,
        "action_type":proposal.action_type,
        "operational_state":state,
        "next_safe_action":registry["next_safe_actions"][state],
        "blocking_reasons":tuple(sorted(set(blocking))),
        "approval_status":approval_status,
        "approval_stale":approval_stale,
        "authority_status":authority_status,
        "authority_expired":authority_expired,
        "execution_outcome":execution_outcome,
        "verification_state":verification_state,
        "reconciliation_state":reconciliation_state,
        "rollback_eligibility":rollback_eligibility,
        "rollback_authorized":False,
        "adapter_health_state":adapter_state,
        "historical_receipt_fingerprints":tuple(sorted(receipts)),
        "lineage_fingerprints":tuple(sorted(lineage)),
        "public_eligible":False,
        "external_action_capability":"NONE",
    }
    item=ExecutionWorkspaceItem(**payload,item_fingerprint=_hash(payload))
    overlap=set(asdict(item)) & set(registry["prohibited_output_fields"])
    if overlap:
        raise ValueError(f"prohibited workspace fields present: {sorted(overlap)}")
    return item


def build_execution_workspace(
    *,
    as_of: str,
    items: Iterable[ExecutionWorkspaceItem],
    registry: Mapping[str,object],
) -> ListingExecutionWorkspace:
    _parse_ts(as_of,"workspace as_of")
    rows=tuple(sorted(tuple(items),key=lambda x:(x.listing_id,x.workspace_item_id)))
    seen=set()
    for item in rows:
        if item.workspace_item_id in seen:
            raise ValueError("duplicate workspace_item_id")
        seen.add(item.workspace_item_id)
        if item.operational_state not in set(registry["operational_states"]):
            raise ValueError("invalid workspace item state")
        if item.public_eligible is not False or item.external_action_capability!="NONE":
            raise ValueError("workspace item authority boundary violated")

    states={state:0 for state in registry["operational_states"]}
    for item in rows:
        states[item.operational_state]+=1
    counts=tuple((state,states[state]) for state in registry["operational_states"])
    blocked=tuple(x.workspace_item_id for x in rows if x.operational_state=="BLOCKED")
    unknown=tuple(x.workspace_item_id for x in rows if "OUTCOME_UNKNOWN" in x.blocking_reasons)
    rollback=tuple(x.workspace_item_id for x in rows if x.rollback_eligibility=="ELIGIBLE")
    payload={
        "as_of":as_of,
        "items":[x.item_fingerprint for x in rows],
        "state_counts":counts,
        "blocked_item_ids":blocked,
        "outcome_unknown_item_ids":unknown,
        "rollback_eligible_item_ids":rollback,
        "public_eligible":False,
        "external_action_capability":"NONE",
    }
    return ListingExecutionWorkspace(
        as_of=as_of,
        items=rows,
        state_counts=counts,
        blocked_item_ids=blocked,
        outcome_unknown_item_ids=unknown,
        rollback_eligible_item_ids=rollback,
        public_eligible=False,
        external_action_capability="NONE",
        workspace_fingerprint=_hash(payload),
    )
