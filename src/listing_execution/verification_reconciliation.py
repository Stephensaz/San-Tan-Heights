from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
import json
from pathlib import Path
from typing import Callable, Iterable, Mapping
import yaml

from src.listing_execution.authorized_execution import (
    AuthorizedAction,
    ExecutionReceipt,
)


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
class VerificationRequest:
    verification_id: str
    receipt_fingerprint: str
    listing_id: str
    action_type: str
    requested_at: str
    verification_key: str
    request_fingerprint: str


@dataclass(frozen=True)
class ObservedStateEvidence:
    observation_id: str
    listing_id: str
    action_type: str
    observed_at: str
    state_code: str
    source_fingerprint: str
    independent: bool
    observation_fingerprint: str


@dataclass(frozen=True)
class VerificationReceipt:
    verification_id: str
    execution_receipt_fingerprint: str
    observation_fingerprint: str | None
    verification_state: str
    expected_outcome: str
    observed_state_code: str | None
    reason_codes: tuple[str,...]
    verified_at: str
    immutable: bool
    verification_fingerprint: str


@dataclass(frozen=True)
class ReconciliationCase:
    reconciliation_case_id: str
    execution_receipt_fingerprint: str
    verification_fingerprint: str
    state: str
    reason_codes: tuple[str,...]
    corrective_action_eligible: bool
    rollback_eligibility: str
    opened_at: str
    case_fingerprint: str


@dataclass(frozen=True)
class RollbackApproval:
    rollback_approval_id: str
    reconciliation_case_fingerprint: str
    actor_id: str
    decision: str
    approved_at: str
    rationale_fingerprint: str
    approval_fingerprint: str


@dataclass(frozen=True)
class RollbackAuthority:
    rollback_authority_id: str
    principal_id: str
    listing_id: str
    allowed_original_action_types: tuple[str,...]
    status: str
    valid_from: str
    valid_until: str
    source_fingerprint: str
    authority_fingerprint: str


@dataclass(frozen=True)
class RollbackRequest:
    rollback_request_id: str
    reconciliation_case_fingerprint: str
    original_proposal_fingerprint: str
    original_authorized_action_fingerprint: str
    original_execution_receipt_fingerprint: str
    verification_fingerprint: str
    rollback_approval_fingerprint: str
    rollback_authority_fingerprint: str
    listing_id: str
    original_action_type: str
    adapter_id: str
    requested_at: str
    idempotency_key: str
    request_fingerprint: str


@dataclass(frozen=True)
class RollbackAdapterResponse:
    adapter_id: str
    request_fingerprint: str
    outcome: str
    external_receipt_id: str | None
    response_fingerprint: str


@dataclass(frozen=True)
class RollbackReceipt:
    rollback_receipt_id: str
    rollback_request_fingerprint: str
    idempotency_key: str
    reconciliation_case_fingerprint: str
    original_execution_receipt_fingerprint: str
    verification_fingerprint: str
    rollback_approval_fingerprint: str
    rollback_authority_fingerprint: str
    outcome: str
    external_receipt_id: str | None
    side_effect_attempted: bool
    duplicate_suppressed: bool
    outcome_unknown: bool
    recorded_at: str
    immutable: bool
    receipt_fingerprint: str


RollbackAdapter = Callable[[RollbackRequest], RollbackAdapterResponse]


def load_verification_registry(path: str|Path) -> dict:
    raw=yaml.safe_load(Path(path).read_text())
    if raw.get("verification_registry_id")!="STH-M12-003-VERIFICATION-RECONCILIATION-v1.0":
        raise ValueError("unexpected M12-003 verification registry id")
    if str(raw.get("version"))!="1.0.0" or raw.get("status")!="FROZEN":
        raise ValueError("M12-003 registry must be FROZEN v1.0")
    if raw.get("ticket")!="M12-003" or raw.get("parent_ticket")!="M12-002":
        raise ValueError("M12-003 registry lineage mismatch")
    return raw


def make_verification_request(
    *,
    verification_id: str,
    receipt: ExecutionReceipt,
    listing_id: str,
    action_type: str,
    requested_at: str,
) -> VerificationRequest:
    if not verification_id.strip():
        raise ValueError("verification_id required")
    _validate_fp(receipt.receipt_fingerprint,"execution receipt fingerprint")
    _parse_ts(requested_at,"verification requested_at")
    key=_hash({
        "execution_receipt_fingerprint":receipt.receipt_fingerprint,
        "listing_id":listing_id,
        "action_type":action_type,
    })
    payload={
        "verification_id":verification_id,
        "receipt_fingerprint":receipt.receipt_fingerprint,
        "listing_id":listing_id,
        "action_type":action_type,
        "requested_at":requested_at,
        "verification_key":key,
    }
    return VerificationRequest(**payload,request_fingerprint=_hash(payload))


def make_observed_state_evidence(
    *,
    observation_id: str,
    listing_id: str,
    action_type: str,
    observed_at: str,
    state_code: str,
    source_fingerprint: str,
    independent: bool,
) -> ObservedStateEvidence:
    if not observation_id.strip() or not state_code.strip():
        raise ValueError("observation_id and state_code required")
    _parse_ts(observed_at,"observed_at")
    _validate_fp(source_fingerprint,"observation source_fingerprint")
    if independent is not True:
        raise ValueError("verification observation must be independently sourced")
    payload={
        "observation_id":observation_id,
        "listing_id":listing_id,
        "action_type":action_type,
        "observed_at":observed_at,
        "state_code":state_code,
        "source_fingerprint":source_fingerprint,
        "independent":True,
    }
    return ObservedStateEvidence(**payload,observation_fingerprint=_hash(payload))


def verify_execution(
    *,
    request: VerificationRequest,
    receipt: ExecutionReceipt,
    observation: ObservedStateEvidence | None,
    expected_state_code: str | None,
    verified_at: str,
    prior_verifications: Iterable[VerificationReceipt],
    registry: Mapping[str,object],
) -> VerificationReceipt:
    _parse_ts(verified_at,"verified_at")
    if request.receipt_fingerprint!=receipt.receipt_fingerprint:
        raise ValueError("verification request receipt binding mismatch")
    if any(x.execution_receipt_fingerprint==receipt.receipt_fingerprint for x in prior_verifications):
        raise ValueError("execution receipt already independently verified")
    reasons=[]
    observed_code=None
    if receipt.outcome in {"DUPLICATE_SUPPRESSED","BLOCKED_OUTCOME_UNKNOWN"} and receipt.side_effect_attempted is False:
        state="NOT_APPLICABLE" if receipt.outcome=="DUPLICATE_SUPPRESSED" else "OUTCOME_UNKNOWN"
        reasons.append(receipt.outcome)
    elif receipt.outcome=="OUTCOME_UNKNOWN":
        state="OUTCOME_UNKNOWN"
        reasons.append("EXECUTION_OUTCOME_UNKNOWN")
    elif observation is None:
        state="OUTCOME_UNKNOWN"
        reasons.append("OBSERVED_STATE_MISSING")
    else:
        if observation.listing_id!=request.listing_id or observation.action_type!=request.action_type:
            raise ValueError("observation scope mismatch")
        if observation.independent is not True:
            raise ValueError("observation is not independent")
        observed_code=observation.state_code
        if expected_state_code is None:
            state="OUTCOME_UNKNOWN"
            reasons.append("EXPECTED_STATE_UNSPECIFIED")
        elif observed_code==expected_state_code:
            state="VERIFIED"
            reasons.append("OBSERVED_STATE_MATCH")
        else:
            state="MISMATCH"
            reasons.append("OBSERVED_STATE_MISMATCH")
    if state not in set(registry["verification"]["states"]):
        raise ValueError("unsupported verification state")
    payload={
        "verification_id":request.verification_id,
        "execution_receipt_fingerprint":receipt.receipt_fingerprint,
        "observation_fingerprint":observation.observation_fingerprint if observation else None,
        "verification_state":state,
        "expected_outcome":receipt.outcome,
        "observed_state_code":observed_code,
        "reason_codes":tuple(sorted(reasons)),
        "verified_at":verified_at,
        "immutable":True,
    }
    return VerificationReceipt(**payload,verification_fingerprint=_hash(payload))


def build_reconciliation_case(
    *,
    reconciliation_case_id: str,
    receipt: ExecutionReceipt,
    verification: VerificationReceipt,
    opened_at: str,
) -> ReconciliationCase | None:
    _parse_ts(opened_at,"reconciliation opened_at")
    if verification.execution_receipt_fingerprint!=receipt.receipt_fingerprint:
        raise ValueError("verification/receipt binding mismatch")
    if verification.verification_state not in {"MISMATCH","OUTCOME_UNKNOWN"}:
        return None
    reasons=tuple(sorted(set(verification.reason_codes)))
    rollback="ELIGIBLE" if verification.verification_state=="MISMATCH" and receipt.side_effect_attempted else "NOT_ELIGIBLE"
    payload={
        "reconciliation_case_id":reconciliation_case_id,
        "execution_receipt_fingerprint":receipt.receipt_fingerprint,
        "verification_fingerprint":verification.verification_fingerprint,
        "state":"OPEN",
        "reason_codes":reasons,
        "corrective_action_eligible":True,
        "rollback_eligibility":rollback,
        "opened_at":opened_at,
    }
    return ReconciliationCase(**payload,case_fingerprint=_hash(payload))


def make_rollback_approval(
    *,
    rollback_approval_id: str,
    reconciliation_case_fingerprint: str,
    actor_id: str,
    decision: str,
    approved_at: str,
    rationale_fingerprint: str,
) -> RollbackApproval:
    if decision not in {"APPROVED","REJECTED"}:
        raise ValueError("unsupported rollback approval decision")
    _validate_fp(reconciliation_case_fingerprint,"reconciliation case fingerprint")
    _validate_fp(rationale_fingerprint,"rollback rationale_fingerprint")
    _parse_ts(approved_at,"rollback approved_at")
    payload={
        "rollback_approval_id":rollback_approval_id,
        "reconciliation_case_fingerprint":reconciliation_case_fingerprint,
        "actor_id":actor_id,
        "decision":decision,
        "approved_at":approved_at,
        "rationale_fingerprint":rationale_fingerprint,
    }
    return RollbackApproval(**payload,approval_fingerprint=_hash(payload))


def make_rollback_authority(
    *,
    rollback_authority_id: str,
    principal_id: str,
    listing_id: str,
    allowed_original_action_types: Iterable[str],
    status: str,
    valid_from: str,
    valid_until: str,
    source_fingerprint: str,
) -> RollbackAuthority:
    start=_parse_ts(valid_from,"rollback authority valid_from")
    end=_parse_ts(valid_until,"rollback authority valid_until")
    if end<=start:
        raise ValueError("rollback authority valid_until must be after valid_from")
    _validate_fp(source_fingerprint,"rollback authority source_fingerprint")
    actions=tuple(sorted(set(allowed_original_action_types)))
    if not actions:
        raise ValueError("rollback authority action scope required")
    payload={
        "rollback_authority_id":rollback_authority_id,
        "principal_id":principal_id,
        "listing_id":listing_id,
        "allowed_original_action_types":actions,
        "status":status,
        "valid_from":valid_from,
        "valid_until":valid_until,
        "source_fingerprint":source_fingerprint,
    }
    return RollbackAuthority(**payload,authority_fingerprint=_hash(payload))


def build_rollback_request(
    *,
    rollback_request_id: str,
    reconciliation_case: ReconciliationCase,
    original_action: AuthorizedAction,
    original_receipt: ExecutionReceipt,
    verification: VerificationReceipt,
    rollback_approval: RollbackApproval,
    rollback_authority: RollbackAuthority,
    adapter_id: str,
    requested_at: str,
) -> RollbackRequest:
    if reconciliation_case.rollback_eligibility!="ELIGIBLE":
        raise ValueError("reconciliation case is not rollback eligible")
    if reconciliation_case.state!="OPEN":
        raise ValueError("reconciliation case is not open")
    if reconciliation_case.execution_receipt_fingerprint!=original_receipt.receipt_fingerprint:
        raise ValueError("rollback original receipt lineage mismatch")
    if reconciliation_case.verification_fingerprint!=verification.verification_fingerprint:
        raise ValueError("rollback verification lineage mismatch")
    if rollback_approval.reconciliation_case_fingerprint!=reconciliation_case.case_fingerprint:
        raise ValueError("rollback approval case binding mismatch")
    if rollback_approval.decision!="APPROVED":
        raise ValueError("explicit rollback approval required")
    if rollback_authority.status!="VALID":
        raise ValueError("rollback authority is not VALID")
    if rollback_authority.listing_id!=original_action.listing_id:
        raise ValueError("rollback authority listing scope mismatch")
    if original_action.action_type not in set(rollback_authority.allowed_original_action_types):
        raise ValueError("rollback authority action scope mismatch")
    when=_parse_ts(requested_at,"rollback requested_at")
    start=_parse_ts(rollback_authority.valid_from,"rollback authority valid_from")
    end=_parse_ts(rollback_authority.valid_until,"rollback authority valid_until")
    if when<start or when>end:
        raise ValueError("rollback authority is not valid at request time")
    idem=_hash({
        "original_proposal_fingerprint":original_action.proposal_fingerprint,
        "original_authorized_action_fingerprint":original_action.authorized_action_fingerprint,
        "original_execution_receipt_fingerprint":original_receipt.receipt_fingerprint,
        "verification_fingerprint":verification.verification_fingerprint,
        "reconciliation_case_fingerprint":reconciliation_case.case_fingerprint,
        "rollback_approval_fingerprint":rollback_approval.approval_fingerprint,
        "rollback_authority_fingerprint":rollback_authority.authority_fingerprint,
        "adapter_id":adapter_id,
    })
    payload={
        "rollback_request_id":rollback_request_id,
        "reconciliation_case_fingerprint":reconciliation_case.case_fingerprint,
        "original_proposal_fingerprint":original_action.proposal_fingerprint,
        "original_authorized_action_fingerprint":original_action.authorized_action_fingerprint,
        "original_execution_receipt_fingerprint":original_receipt.receipt_fingerprint,
        "verification_fingerprint":verification.verification_fingerprint,
        "rollback_approval_fingerprint":rollback_approval.approval_fingerprint,
        "rollback_authority_fingerprint":rollback_authority.authority_fingerprint,
        "listing_id":original_action.listing_id,
        "original_action_type":original_action.action_type,
        "adapter_id":adapter_id,
        "requested_at":requested_at,
        "idempotency_key":idem,
    }
    return RollbackRequest(**payload,request_fingerprint=_hash(payload))


def make_rollback_adapter_response(
    *,
    adapter_id: str,
    request_fingerprint: str,
    outcome: str,
    external_receipt_id: str | None,
    registry: Mapping[str,object],
) -> RollbackAdapterResponse:
    _validate_fp(request_fingerprint,"rollback request_fingerprint")
    if outcome not in set(registry["rollback"]["allowed_adapter_outcomes"]):
        raise ValueError("unsupported rollback adapter outcome")
    payload={
        "adapter_id":adapter_id,
        "request_fingerprint":request_fingerprint,
        "outcome":outcome,
        "external_receipt_id":external_receipt_id,
    }
    return RollbackAdapterResponse(**payload,response_fingerprint=_hash(payload))


def execute_rollback(
    *,
    rollback_receipt_id: str,
    request: RollbackRequest,
    reconciliation_case: ReconciliationCase,
    rollback_approval: RollbackApproval,
    rollback_authority: RollbackAuthority,
    adapter: RollbackAdapter,
    prior_receipts: Iterable[RollbackReceipt],
    execution_at: str,
    registry: Mapping[str,object],
) -> RollbackReceipt:
    if request.reconciliation_case_fingerprint!=reconciliation_case.case_fingerprint:
        raise ValueError("rollback request case binding mismatch")
    if request.rollback_approval_fingerprint!=rollback_approval.approval_fingerprint:
        raise ValueError("rollback request approval binding mismatch")
    if request.rollback_authority_fingerprint!=rollback_authority.authority_fingerprint:
        raise ValueError("rollback request authority binding mismatch")
    if rollback_approval.decision!="APPROVED":
        raise ValueError("explicit rollback approval required")
    when=_parse_ts(execution_at,"rollback execution_at")
    start=_parse_ts(rollback_authority.valid_from,"rollback authority valid_from")
    end=_parse_ts(rollback_authority.valid_until,"rollback authority valid_until")
    if rollback_authority.status!="VALID" or when<start or when>end:
        raise ValueError("rollback authority is not valid at execution time")

    previous=[x for x in prior_receipts if x.idempotency_key==request.idempotency_key]
    if previous:
        if any(x.outcome=="OUTCOME_UNKNOWN" for x in previous):
            outcome="BLOCKED_OUTCOME_UNKNOWN"
        else:
            outcome="DUPLICATE_SUPPRESSED"
        return _rollback_receipt(
            rollback_receipt_id=rollback_receipt_id,request=request,outcome=outcome,
            external_receipt_id=None,side_effect_attempted=False,duplicate_suppressed=True,
            recorded_at=execution_at,
        )

    try:
        response=adapter(request)
    except Exception:
        return _rollback_receipt(
            rollback_receipt_id=rollback_receipt_id,request=request,outcome="OUTCOME_UNKNOWN",
            external_receipt_id=None,side_effect_attempted=True,duplicate_suppressed=False,
            recorded_at=execution_at,
        )
    outcome=response.outcome
    external=response.external_receipt_id
    if response.adapter_id!=request.adapter_id or response.request_fingerprint!=request.request_fingerprint:
        outcome="OUTCOME_UNKNOWN"; external=None
    elif outcome=="SUCCEEDED" and not external:
        outcome="OUTCOME_UNKNOWN"; external=None
    return _rollback_receipt(
        rollback_receipt_id=rollback_receipt_id,request=request,outcome=outcome,
        external_receipt_id=external,side_effect_attempted=True,duplicate_suppressed=False,
        recorded_at=execution_at,
    )


def _rollback_receipt(
    *,
    rollback_receipt_id: str,
    request: RollbackRequest,
    outcome: str,
    external_receipt_id: str | None,
    side_effect_attempted: bool,
    duplicate_suppressed: bool,
    recorded_at: str,
) -> RollbackReceipt:
    payload={
        "rollback_receipt_id":rollback_receipt_id,
        "rollback_request_fingerprint":request.request_fingerprint,
        "idempotency_key":request.idempotency_key,
        "reconciliation_case_fingerprint":request.reconciliation_case_fingerprint,
        "original_execution_receipt_fingerprint":request.original_execution_receipt_fingerprint,
        "verification_fingerprint":request.verification_fingerprint,
        "rollback_approval_fingerprint":request.rollback_approval_fingerprint,
        "rollback_authority_fingerprint":request.rollback_authority_fingerprint,
        "outcome":outcome,
        "external_receipt_id":external_receipt_id,
        "side_effect_attempted":side_effect_attempted,
        "duplicate_suppressed":duplicate_suppressed,
        "outcome_unknown":outcome in {"OUTCOME_UNKNOWN","BLOCKED_OUTCOME_UNKNOWN"},
        "recorded_at":recorded_at,
        "immutable":True,
    }
    return RollbackReceipt(**payload,receipt_fingerprint=_hash(payload))
