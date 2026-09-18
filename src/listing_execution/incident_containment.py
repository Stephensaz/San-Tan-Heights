from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
from typing import Iterable, Mapping
import yaml

from src.listing_execution.authorized_execution import (
    Adapter,
    AuthorizedAction,
    ExecutionAuthority,
    ExecutionReceipt,
    HumanApproval,
    ExecutionRequest,
    execute_authorized_action,
)
from src.listing_execution.action_planning import GovernedActionProposal
from src.listing_execution.execution_workspace import ExecutionWorkspaceItem
from src.listing_execution.verification_reconciliation import ReconciliationCase


def _hash(payload: object) -> str:
    raw=json.dumps(payload,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode("utf-8")
    return sha256(raw).hexdigest()


@dataclass(frozen=True)
class OperationalIncident:
    incident_id: str
    incident_type: str
    state: str
    workspace_item_id: str
    listing_id: str
    proposal_fingerprint: str
    action_type: str
    adapter_id: str | None
    evidence_fingerprints: tuple[str,...]
    blast_radius: tuple[str,...]
    incident_fingerprint: str


@dataclass(frozen=True)
class ExecutionHold:
    hold_id: str
    incident_fingerprint: str
    scope: str
    target_id: str
    state: str
    reason: str
    lineage_fingerprints: tuple[str,...]
    hold_fingerprint: str


@dataclass(frozen=True)
class HoldReleaseDecision:
    release_id: str
    hold_fingerprint: str
    actor_id: str
    decision: str
    rationale_fingerprint: str
    release_fingerprint: str


@dataclass(frozen=True)
class RecoveryValidation:
    validation_id: str
    hold_fingerprint: str
    prerequisite_fingerprint: str
    authority_fingerprint: str
    prerequisites_current: bool
    authority_current: bool
    independently_reconciled: bool
    validation_fingerprint: str


@dataclass(frozen=True)
class RecoveryEvidence:
    recovery_id: str
    incident_fingerprint: str
    hold_fingerprint: str
    release_fingerprint: str
    validation_fingerprint: str
    state: str
    lineage_fingerprints: tuple[str,...]
    recovery_fingerprint: str


def load_incident_registry(path: str|Path) -> dict:
    raw=yaml.safe_load(Path(path).read_text())
    if raw.get("incident_registry_id")!="STH-M12-007-INCIDENT-CONTAINMENT-v1.0":
        raise ValueError("unexpected M12-007 incident registry id")
    if str(raw.get("version"))!="1.0.0" or raw.get("status")!="FROZEN":
        raise ValueError("M12-007 registry must be FROZEN v1.0")
    return raw


def detect_incidents(
    *,
    items: Iterable[ExecutionWorkspaceItem],
    adapter_ids: Mapping[str,str] | None,
    registry: Mapping[str,object],
) -> tuple[OperationalIncident,...]:
    adapter_ids=adapter_ids or {}
    incidents=[]
    unknown_count=0
    rows=tuple(sorted(items,key=lambda x:x.workspace_item_id))
    for item in rows:
        conditions=[]
        if item.adapter_health_state=="DEGRADED":
            conditions.append("ADAPTER_DEGRADED")
        if item.adapter_health_state=="UNAVAILABLE":
            conditions.append("ADAPTER_UNAVAILABLE")
        if "OUTCOME_UNKNOWN" in item.blocking_reasons:
            conditions.append("OUTCOME_UNKNOWN")
            unknown_count+=1
        if "OPEN_RECONCILIATION" in item.blocking_reasons:
            conditions.append("OPEN_RECONCILIATION")
        if item.authority_expired or item.authority_status not in {"VALID","MISSING"}:
            conditions.append("AUTHORITY_ANOMALY")
        for kind in conditions:
            evidence=tuple(sorted(set(item.lineage_fingerprints) | {item.item_fingerprint}))
            blast=tuple(sorted({f"ACTION:{item.proposal_fingerprint}",f"LISTING:{item.listing_id}"} | ({f"ADAPTER:{adapter_ids[item.workspace_item_id]}"} if item.workspace_item_id in adapter_ids else set())))
            payload={
                "incident_id":f"INC-{item.workspace_item_id}-{kind}",
                "incident_type":kind,
                "state":"OPEN",
                "workspace_item_id":item.workspace_item_id,
                "listing_id":item.listing_id,
                "proposal_fingerprint":item.proposal_fingerprint,
                "action_type":item.action_type,
                "adapter_id":adapter_ids.get(item.workspace_item_id),
                "evidence_fingerprints":evidence,
                "blast_radius":blast,
            }
            incidents.append(OperationalIncident(**payload,incident_fingerprint=_hash(payload)))
    if unknown_count>=2 and rows:
        fps=tuple(sorted(x.item_fingerprint for x in rows if "OUTCOME_UNKNOWN" in x.blocking_reasons))
        payload={
            "incident_id":"INC-PORTFOLIO-REPEATED_OUTCOME_UNKNOWN",
            "incident_type":"REPEATED_OUTCOME_UNKNOWN",
            "state":"OPEN",
            "workspace_item_id":"PORTFOLIO",
            "listing_id":"MULTIPLE",
            "proposal_fingerprint":"0"*64,
            "action_type":"MULTIPLE",
            "adapter_id":None,
            "evidence_fingerprints":fps,
            "blast_radius":tuple(sorted(f"LISTING:{x.listing_id}" for x in rows if "OUTCOME_UNKNOWN" in x.blocking_reasons)),
        }
        incidents.append(OperationalIncident(**payload,incident_fingerprint=_hash(payload)))
    allowed=set(registry["incident_types"])
    if any(x.incident_type not in allowed for x in incidents):
        raise ValueError("unsupported incident type")
    return tuple(sorted(incidents,key=lambda x:x.incident_id))


def create_execution_hold(
    *,
    hold_id: str,
    incident: OperationalIncident,
    scope: str,
    target_id: str,
    registry: Mapping[str,object],
) -> ExecutionHold:
    if scope not in set(registry["hold_scopes"]):
        raise ValueError("unsupported hold scope")
    expected=f"{scope}:{target_id}"
    if expected not in set(incident.blast_radius):
        raise ValueError("hold target outside incident blast radius")
    payload={
        "hold_id":hold_id,
        "incident_fingerprint":incident.incident_fingerprint,
        "scope":scope,
        "target_id":target_id,
        "state":"ACTIVE",
        "reason":incident.incident_type,
        "lineage_fingerprints":tuple(sorted(set(incident.evidence_fingerprints) | {incident.incident_fingerprint})),
    }
    return ExecutionHold(**payload,hold_fingerprint=_hash(payload))


def make_hold_release_decision(
    *,
    release_id: str,
    hold: ExecutionHold,
    actor_id: str,
    decision: str,
    rationale_fingerprint: str,
    registry: Mapping[str,object],
) -> HoldReleaseDecision:
    if decision not in set(registry["release_decisions"]):
        raise ValueError("unsupported hold release decision")
    payload={
        "release_id":release_id,
        "hold_fingerprint":hold.hold_fingerprint,
        "actor_id":actor_id,
        "decision":decision,
        "rationale_fingerprint":rationale_fingerprint,
    }
    return HoldReleaseDecision(**payload,release_fingerprint=_hash(payload))


def make_recovery_validation(
    *,
    validation_id: str,
    hold: ExecutionHold,
    prerequisite_fingerprint: str,
    authority_fingerprint: str,
    prerequisites_current: bool,
    authority_current: bool,
    independently_reconciled: bool,
) -> RecoveryValidation:
    payload={
        "validation_id":validation_id,
        "hold_fingerprint":hold.hold_fingerprint,
        "prerequisite_fingerprint":prerequisite_fingerprint,
        "authority_fingerprint":authority_fingerprint,
        "prerequisites_current":prerequisites_current,
        "authority_current":authority_current,
        "independently_reconciled":independently_reconciled,
    }
    return RecoveryValidation(**payload,validation_fingerprint=_hash(payload))


def close_incident_with_recovery(
    *,
    recovery_id: str,
    incident: OperationalIncident,
    hold: ExecutionHold,
    release: HoldReleaseDecision,
    validation: RecoveryValidation,
    reconciliation_case: ReconciliationCase | None,
) -> RecoveryEvidence:
    if release.hold_fingerprint!=hold.hold_fingerprint or validation.hold_fingerprint!=hold.hold_fingerprint:
        raise ValueError("recovery hold lineage mismatch")
    if release.decision!="RELEASE":
        raise ValueError("explicit human RELEASE decision required")
    if not validation.prerequisites_current or not validation.authority_current:
        raise ValueError("fresh prerequisite and authority revalidation required")
    if incident.incident_type in {"OUTCOME_UNKNOWN","REPEATED_OUTCOME_UNKNOWN"}:
        if reconciliation_case is None or reconciliation_case.state!="RESOLVED" or not validation.independently_reconciled:
            raise ValueError("outcome-unknown cannot close before independent reconciliation")
    lineage=tuple(sorted({
        incident.incident_fingerprint,hold.hold_fingerprint,release.release_fingerprint,
        validation.validation_fingerprint,
    } | ({reconciliation_case.case_fingerprint} if reconciliation_case else set())))
    payload={
        "recovery_id":recovery_id,
        "incident_fingerprint":incident.incident_fingerprint,
        "hold_fingerprint":hold.hold_fingerprint,
        "release_fingerprint":release.release_fingerprint,
        "validation_fingerprint":validation.validation_fingerprint,
        "state":"RECOVERED",
        "lineage_fingerprints":lineage,
    }
    return RecoveryEvidence(**payload,recovery_fingerprint=_hash(payload))


def _hold_matches(hold: ExecutionHold, proposal: GovernedActionProposal, request: ExecutionRequest) -> bool:
    if hold.state!="ACTIVE":
        return False
    if hold.scope=="ACTION":
        return hold.target_id==proposal.proposal_fingerprint
    if hold.scope=="LISTING":
        return hold.target_id==proposal.listing_id
    if hold.scope=="ADAPTER":
        return hold.target_id==request.adapter_id
    return False


def execute_with_incident_guard(
    *,
    active_holds: Iterable[ExecutionHold],
    receipt_id: str,
    proposal: GovernedActionProposal,
    approval: HumanApproval,
    authority: ExecutionAuthority,
    authorized_action: AuthorizedAction,
    request: ExecutionRequest,
    adapter: Adapter,
    prior_receipts: Iterable[ExecutionReceipt],
    execution_at: str,
    execution_registry: Mapping[str,object],
) -> ExecutionReceipt:
    holds=tuple(active_holds)
    if any(_hold_matches(h,proposal,request) for h in holds):
        raise ValueError("execution blocked by active incident hold")
    return execute_authorized_action(
        receipt_id=receipt_id,proposal=proposal,approval=approval,authority=authority,
        authorized_action=authorized_action,request=request,adapter=adapter,
        prior_receipts=prior_receipts,execution_at=execution_at,registry=execution_registry,
    )
