from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from hashlib import sha256
import json
from pathlib import Path
from typing import Callable, Iterable, Mapping
import yaml

from src.listing_execution.action_planning import GovernedActionProposal


def _hash(payload: object) -> str:
    raw=json.dumps(payload,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode("utf-8")
    return sha256(raw).hexdigest()


def _validate_fp(value: str, label: str) -> None:
    if len(value)!=64 or any(c not in "0123456789abcdef" for c in value):
        raise ValueError(f"{label} must be lowercase sha256")


def _parse_ts(value: str, label: str) -> datetime:
    try:
        dt=datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{label} must be ISO-8601") from exc
    if dt.tzinfo is None:
        raise ValueError(f"{label} must include timezone")
    return dt


@dataclass(frozen=True)
class HumanApproval:
    approval_id: str
    proposal_fingerprint: str
    actor_id: str
    decision: str
    approved_at: str
    rationale_fingerprint: str
    approval_fingerprint: str


@dataclass(frozen=True)
class ExecutionAuthority:
    authority_id: str
    principal_id: str
    listing_id: str
    allowed_action_types: tuple[str,...]
    status: str
    valid_from: str
    valid_until: str
    source_fingerprint: str
    authority_fingerprint: str


@dataclass(frozen=True)
class AuthorizedAction:
    authorized_action_id: str
    proposal_id: str
    proposal_fingerprint: str
    listing_id: str
    subject_property_id: str
    action_type: str
    approval_id: str
    approval_fingerprint: str
    authority_id: str
    authority_fingerprint: str
    authorization_state: str
    execution_state: str
    authorized_at: str
    lineage_fingerprints: tuple[str,...]
    public_eligible: bool
    authorized_action_fingerprint: str


@dataclass(frozen=True)
class ExecutionRequest:
    request_id: str
    authorized_action_fingerprint: str
    proposal_fingerprint: str
    listing_id: str
    action_type: str
    adapter_id: str
    requested_at: str
    idempotency_key: str
    request_fingerprint: str


@dataclass(frozen=True)
class AdapterResponse:
    adapter_id: str
    request_fingerprint: str
    outcome: str
    external_receipt_id: str | None
    response_fingerprint: str


@dataclass(frozen=True)
class ExecutionReceipt:
    receipt_id: str
    request_id: str
    request_fingerprint: str
    idempotency_key: str
    proposal_fingerprint: str
    authorized_action_fingerprint: str
    approval_fingerprint: str
    authority_fingerprint: str
    adapter_id: str
    adapter_response_fingerprint: str | None
    outcome: str
    external_receipt_id: str | None
    side_effect_attempted: bool
    duplicate_suppressed: bool
    outcome_unknown: bool
    recorded_at: str
    lineage_fingerprints: tuple[str,...]
    immutable: bool
    public_eligible: bool
    receipt_fingerprint: str


Adapter = Callable[[ExecutionRequest], AdapterResponse]


def load_execution_registry(path: str|Path) -> dict:
    raw=yaml.safe_load(Path(path).read_text())
    if raw.get("execution_registry_id")!="STH-M12-002-AUTHORIZED-EXECUTION-v1.0":
        raise ValueError("unexpected M12-002 execution registry id")
    if str(raw.get("version"))!="1.0.0" or raw.get("status")!="FROZEN":
        raise ValueError("M12-002 registry must be FROZEN v1.0")
    if raw.get("ticket")!="M12-002" or raw.get("parent_ticket")!="M12-001":
        raise ValueError("M12-002 registry lineage mismatch")
    return raw


def make_human_approval(
    *,
    approval_id: str,
    proposal_fingerprint: str,
    actor_id: str,
    decision: str,
    approved_at: str,
    rationale_fingerprint: str,
    registry: Mapping[str,object],
) -> HumanApproval:
    if not approval_id.strip() or not actor_id.strip():
        raise ValueError("approval_id and actor_id required")
    _validate_fp(proposal_fingerprint,"proposal_fingerprint")
    _validate_fp(rationale_fingerprint,"rationale_fingerprint")
    if decision not in set(registry["approval"]["allowed_decisions"]):
        raise ValueError("unsupported approval decision")
    _parse_ts(approved_at,"approved_at")
    payload={
        "approval_id":approval_id,
        "proposal_fingerprint":proposal_fingerprint,
        "actor_id":actor_id,
        "decision":decision,
        "approved_at":approved_at,
        "rationale_fingerprint":rationale_fingerprint,
    }
    return HumanApproval(
        approval_id=approval_id,
        proposal_fingerprint=proposal_fingerprint,
        actor_id=actor_id,
        decision=decision,
        approved_at=approved_at,
        rationale_fingerprint=rationale_fingerprint,
        approval_fingerprint=_hash(payload),
    )


def make_execution_authority(
    *,
    authority_id: str,
    principal_id: str,
    listing_id: str,
    allowed_action_types: Iterable[str],
    status: str,
    valid_from: str,
    valid_until: str,
    source_fingerprint: str,
    registry: Mapping[str,object],
) -> ExecutionAuthority:
    if not authority_id.strip() or not principal_id.strip() or not listing_id.strip():
        raise ValueError("authority id, principal id, and listing id required")
    start=_parse_ts(valid_from,"authority valid_from")
    end=_parse_ts(valid_until,"authority valid_until")
    if end<=start:
        raise ValueError("authority valid_until must be after valid_from")
    _validate_fp(source_fingerprint,"authority source_fingerprint")
    actions=tuple(sorted(set(str(x) for x in allowed_action_types)))
    if not actions:
        raise ValueError("authority action scope required")
    payload={
        "authority_id":authority_id,
        "principal_id":principal_id,
        "listing_id":listing_id,
        "allowed_action_types":actions,
        "status":status,
        "valid_from":valid_from,
        "valid_until":valid_until,
        "source_fingerprint":source_fingerprint,
    }
    return ExecutionAuthority(
        authority_id=authority_id,
        principal_id=principal_id,
        listing_id=listing_id,
        allowed_action_types=actions,
        status=status,
        valid_from=valid_from,
        valid_until=valid_until,
        source_fingerprint=source_fingerprint,
        authority_fingerprint=_hash(payload),
    )


def _validate_proposal(proposal: GovernedActionProposal) -> None:
    _validate_fp(proposal.proposal_fingerprint,"proposal fingerprint")
    if proposal.proposal_status!="PROPOSED":
        raise ValueError("M12-002 requires current PROPOSED action")
    if proposal.approval_state!="NOT_APPROVED" or proposal.authorization_state!="NOT_AUTHORIZED":
        raise ValueError("M12-001 proposal authority state is not pristine")
    if proposal.execution_state!="NOT_EXECUTABLE":
        raise ValueError("M12-001 proposal execution state is not pristine")
    if proposal.public_eligible is not False or proposal.external_action_capability!="NONE":
        raise ValueError("M12-001 proposal boundary violated")


def _validate_authority(
    *,
    proposal: GovernedActionProposal,
    approval: HumanApproval,
    authority: ExecutionAuthority,
    at: str,
    registry: Mapping[str,object],
) -> datetime:
    when=_parse_ts(at,"authority validation timestamp")
    if approval.proposal_fingerprint!=proposal.proposal_fingerprint:
        raise ValueError("approval is not bound to exact proposal")
    if approval.decision!=registry["approval"]["required_for_authorization"]:
        raise ValueError("explicit APPROVED human approval required")
    if authority.status!=registry["authority"]["required_status"]:
        raise ValueError("execution authority is not VALID")
    if authority.listing_id!=proposal.listing_id:
        raise ValueError("execution authority listing scope mismatch")
    if proposal.action_type not in set(authority.allowed_action_types):
        raise ValueError("execution authority action scope mismatch")
    start=_parse_ts(authority.valid_from,"authority valid_from")
    end=_parse_ts(authority.valid_until,"authority valid_until")
    if when<start or when>end:
        raise ValueError("execution authority is not valid at requested time")
    return when


def authorize_action(
    *,
    authorized_action_id: str,
    proposal: GovernedActionProposal,
    approval: HumanApproval,
    authority: ExecutionAuthority,
    authorized_at: str,
    registry: Mapping[str,object],
) -> AuthorizedAction:
    if not authorized_action_id.strip():
        raise ValueError("authorized_action_id required")
    _validate_proposal(proposal)
    _validate_authority(
        proposal=proposal,approval=approval,authority=authority,at=authorized_at,registry=registry
    )
    lineage=tuple(sorted({
        proposal.proposal_fingerprint,
        approval.approval_fingerprint,
        approval.rationale_fingerprint,
        authority.authority_fingerprint,
        authority.source_fingerprint,
    }))
    payload={
        "authorized_action_id":authorized_action_id,
        "proposal_id":proposal.proposal_id,
        "proposal_fingerprint":proposal.proposal_fingerprint,
        "listing_id":proposal.listing_id,
        "subject_property_id":proposal.subject_property_id,
        "action_type":proposal.action_type,
        "approval_id":approval.approval_id,
        "approval_fingerprint":approval.approval_fingerprint,
        "authority_id":authority.authority_id,
        "authority_fingerprint":authority.authority_fingerprint,
        "authorization_state":registry["execution"]["authorized_state"],
        "execution_state":registry["execution"]["ready_state"],
        "authorized_at":authorized_at,
        "lineage_fingerprints":lineage,
        "public_eligible":False,
    }
    return AuthorizedAction(**payload,authorized_action_fingerprint=_hash(payload))


def build_execution_request(
    *,
    request_id: str,
    authorized_action: AuthorizedAction,
    adapter_id: str,
    requested_at: str,
) -> ExecutionRequest:
    if not request_id.strip() or not adapter_id.strip():
        raise ValueError("request_id and adapter_id required")
    _parse_ts(requested_at,"execution request requested_at")
    idempotency_key=_hash({
        "proposal_fingerprint":authorized_action.proposal_fingerprint,
        "approval_fingerprint":authorized_action.approval_fingerprint,
        "authority_fingerprint":authorized_action.authority_fingerprint,
        "action_type":authorized_action.action_type,
        "listing_id":authorized_action.listing_id,
        "adapter_id":adapter_id,
    })
    payload={
        "request_id":request_id,
        "authorized_action_fingerprint":authorized_action.authorized_action_fingerprint,
        "proposal_fingerprint":authorized_action.proposal_fingerprint,
        "listing_id":authorized_action.listing_id,
        "action_type":authorized_action.action_type,
        "adapter_id":adapter_id,
        "requested_at":requested_at,
        "idempotency_key":idempotency_key,
    }
    return ExecutionRequest(**payload,request_fingerprint=_hash(payload))


def make_adapter_response(
    *,
    adapter_id: str,
    request_fingerprint: str,
    outcome: str,
    external_receipt_id: str | None,
    registry: Mapping[str,object],
) -> AdapterResponse:
    _validate_fp(request_fingerprint,"request_fingerprint")
    if outcome not in set(registry["execution"]["allowed_adapter_outcomes"]):
        raise ValueError("unsupported adapter outcome")
    payload={
        "adapter_id":adapter_id,
        "request_fingerprint":request_fingerprint,
        "outcome":outcome,
        "external_receipt_id":external_receipt_id,
    }
    return AdapterResponse(
        adapter_id=adapter_id,
        request_fingerprint=request_fingerprint,
        outcome=outcome,
        external_receipt_id=external_receipt_id,
        response_fingerprint=_hash(payload),
    )


def _receipt(
    *,
    receipt_id: str,
    request: ExecutionRequest,
    authorized_action: AuthorizedAction,
    approval: HumanApproval,
    authority: ExecutionAuthority,
    outcome: str,
    external_receipt_id: str | None,
    adapter_response_fingerprint: str | None,
    side_effect_attempted: bool,
    duplicate_suppressed: bool,
    recorded_at: str,
) -> ExecutionReceipt:
    lineage={
        request.request_fingerprint,
        authorized_action.authorized_action_fingerprint,
        authorized_action.proposal_fingerprint,
        approval.approval_fingerprint,
        authority.authority_fingerprint,
    }
    if adapter_response_fingerprint:
        lineage.add(adapter_response_fingerprint)
    lineage_tuple=tuple(sorted(lineage))
    payload={
        "receipt_id":receipt_id,
        "request_id":request.request_id,
        "request_fingerprint":request.request_fingerprint,
        "idempotency_key":request.idempotency_key,
        "proposal_fingerprint":authorized_action.proposal_fingerprint,
        "authorized_action_fingerprint":authorized_action.authorized_action_fingerprint,
        "approval_fingerprint":approval.approval_fingerprint,
        "authority_fingerprint":authority.authority_fingerprint,
        "adapter_id":request.adapter_id,
        "adapter_response_fingerprint":adapter_response_fingerprint,
        "outcome":outcome,
        "external_receipt_id":external_receipt_id,
        "side_effect_attempted":side_effect_attempted,
        "duplicate_suppressed":duplicate_suppressed,
        "outcome_unknown":outcome in {"OUTCOME_UNKNOWN","BLOCKED_OUTCOME_UNKNOWN"},
        "recorded_at":recorded_at,
        "lineage_fingerprints":lineage_tuple,
        "immutable":True,
        "public_eligible":False,
    }
    return ExecutionReceipt(**payload,receipt_fingerprint=_hash(payload))


def execute_authorized_action(
    *,
    receipt_id: str,
    proposal: GovernedActionProposal,
    approval: HumanApproval,
    authority: ExecutionAuthority,
    authorized_action: AuthorizedAction,
    request: ExecutionRequest,
    adapter: Adapter,
    prior_receipts: Iterable[ExecutionReceipt],
    execution_at: str,
    registry: Mapping[str,object],
) -> ExecutionReceipt:
    if not receipt_id.strip():
        raise ValueError("receipt_id required")
    _validate_proposal(proposal)
    if authorized_action.proposal_fingerprint!=proposal.proposal_fingerprint:
        raise ValueError("authorized action proposal binding mismatch")
    if authorized_action.approval_fingerprint!=approval.approval_fingerprint:
        raise ValueError("authorized action approval binding mismatch")
    if authorized_action.authority_fingerprint!=authority.authority_fingerprint:
        raise ValueError("authorized action authority binding mismatch")
    if request.authorized_action_fingerprint!=authorized_action.authorized_action_fingerprint:
        raise ValueError("request authorized-action binding mismatch")
    if request.proposal_fingerprint!=proposal.proposal_fingerprint:
        raise ValueError("request proposal binding mismatch")

    # Mandatory immediate revalidation before any adapter call.
    _validate_authority(
        proposal=proposal,approval=approval,authority=authority,at=execution_at,registry=registry
    )

    previous=[x for x in prior_receipts if x.idempotency_key==request.idempotency_key]
    if previous:
        previous=sorted(previous,key=lambda x:(x.recorded_at,x.receipt_id))
        if any(x.outcome in {"OUTCOME_UNKNOWN","BLOCKED_OUTCOME_UNKNOWN"} for x in previous):
            return _receipt(
                receipt_id=receipt_id,request=request,authorized_action=authorized_action,
                approval=approval,authority=authority,outcome="BLOCKED_OUTCOME_UNKNOWN",
                external_receipt_id=None,adapter_response_fingerprint=None,
                side_effect_attempted=False,duplicate_suppressed=True,recorded_at=execution_at,
            )
        return _receipt(
            receipt_id=receipt_id,request=request,authorized_action=authorized_action,
            approval=approval,authority=authority,outcome="DUPLICATE_SUPPRESSED",
            external_receipt_id=None,adapter_response_fingerprint=None,
            side_effect_attempted=False,duplicate_suppressed=True,recorded_at=execution_at,
        )

    try:
        response=adapter(request)
    except Exception:
        return _receipt(
            receipt_id=receipt_id,request=request,authorized_action=authorized_action,
            approval=approval,authority=authority,outcome="OUTCOME_UNKNOWN",
            external_receipt_id=None,adapter_response_fingerprint=None,
            side_effect_attempted=True,duplicate_suppressed=False,recorded_at=execution_at,
        )

    if response.adapter_id!=request.adapter_id or response.request_fingerprint!=request.request_fingerprint:
        return _receipt(
            receipt_id=receipt_id,request=request,authorized_action=authorized_action,
            approval=approval,authority=authority,outcome="OUTCOME_UNKNOWN",
            external_receipt_id=None,adapter_response_fingerprint=response.response_fingerprint,
            side_effect_attempted=True,duplicate_suppressed=False,recorded_at=execution_at,
        )

    outcome=response.outcome
    external=response.external_receipt_id
    if outcome=="SUCCEEDED" and not external:
        outcome="OUTCOME_UNKNOWN"
    if outcome=="OUTCOME_UNKNOWN":
        external=None

    return _receipt(
        receipt_id=receipt_id,request=request,authorized_action=authorized_action,
        approval=approval,authority=authority,outcome=outcome,
        external_receipt_id=external,adapter_response_fingerprint=response.response_fingerprint,
        side_effect_attempted=True,duplicate_suppressed=False,recorded_at=execution_at,
    )
