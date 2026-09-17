from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from hashlib import sha256
from typing import Any, Mapping, Protocol
from uuid import UUID, uuid4

from src.production_certification.approval.limited import LimitedApproval
from src.production_certification.cohort.membership import FrozenCohortMembership
from src.production_certification.go_live.stop_conditions import GoLiveStopResult
from src.shared.canonical_json import canonical_json


class CohortDeploymentExecutor(Protocol):
    def deploy(self, *, property_id: UUID, variants: tuple[str, ...], candidate_fingerprint: str) -> Mapping[str, Any]: ...


@dataclass(frozen=True)
class CohortDeploymentItem:
    property_id: UUID
    membership_ordinal: int
    status: str
    evidence_hash: str
    detail: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CohortDeployment:
    cohort_deployment_id: UUID
    cohort_id: UUID
    production_certification_id: UUID
    candidate_fingerprint: str
    limited_approval_fingerprint: str
    membership_fingerprint: str
    deployment_status: str
    items: tuple[CohortDeploymentItem, ...]
    deployment_fingerprint: str
    deployed_by: str
    started_at: datetime
    completed_at: datetime


class Cohort25DeploymentService:
    def deploy(
        self,
        *,
        membership: FrozenCohortMembership,
        approval: LimitedApproval,
        current_stop_conditions: GoLiveStopResult,
        executor: CohortDeploymentExecutor,
        deployed_by: str,
        started_at: datetime | None = None,
        deployment_id: UUID | None = None,
    ) -> CohortDeployment:
        if membership.cohort_code != "COHORT_25" or len(membership.property_ids) != 25:
            raise ValueError("COHORT_25 requires exactly 25 frozen properties")
        if not deployed_by.strip():
            raise ValueError("deployed_by is required")
        if approval.limited_approval_id != membership.limited_approval_id or approval.approval_fingerprint != membership.limited_approval_fingerprint:
            raise ValueError("limited approval does not match frozen cohort")
        if approval.production_certification_id != membership.production_certification_id:
            raise ValueError("certification identity mismatch")
        if approval.candidate_fingerprint != membership.candidate_fingerprint:
            raise ValueError("candidate fingerprint mismatch")
        now = started_at or datetime.now(timezone.utc)
        if now.tzinfo is None:
            raise ValueError("started_at must be timezone-aware")
        if not (approval.issued_at <= now < approval.expires_at):
            raise ValueError("limited approval is not active")
        if current_stop_conditions.production_certification_id != membership.production_certification_id or current_stop_conditions.status != "CLEAR":
            raise ValueError("go-live stop conditions are not clear")
        items: list[CohortDeploymentItem] = []
        for ordinal, property_id in enumerate(membership.property_ids, start=1):
            try:
                detail = dict(executor.deploy(
                    property_id=property_id,
                    variants=membership.allowed_variants,
                    candidate_fingerprint=membership.candidate_fingerprint,
                ))
                status = "PASS"
            except Exception as exc:  # evidence boundary; do not continue silently
                detail = {"error_type": exc.__class__.__name__, "error": str(exc)}
                status = "FAIL"
            evidence_payload = {
                "property_id": str(property_id), "membership_ordinal": ordinal,
                "status": status, "detail": detail,
            }
            evidence_hash = sha256(canonical_json(evidence_payload).encode("utf-8")).hexdigest()
            items.append(CohortDeploymentItem(property_id, ordinal, status, evidence_hash, detail))
            if status == "FAIL":
                break
        status = "PASS" if len(items) == 25 and all(x.status == "PASS" for x in items) else "FAIL"
        did = deployment_id or uuid4()
        completed = datetime.now(timezone.utc)
        payload = {
            "cohort_deployment_id": str(did), "cohort_id": str(membership.cohort_id),
            "production_certification_id": str(membership.production_certification_id),
            "candidate_fingerprint": membership.candidate_fingerprint,
            "limited_approval_fingerprint": membership.limited_approval_fingerprint,
            "membership_fingerprint": membership.membership_fingerprint,
            "deployment_status": status,
            "item_evidence_hashes": [x.evidence_hash for x in items],
        }
        fp = sha256(canonical_json(payload).encode("utf-8")).hexdigest()
        return CohortDeployment(did, membership.cohort_id, membership.production_certification_id,
            membership.candidate_fingerprint, membership.limited_approval_fingerprint,
            membership.membership_fingerprint, status, tuple(items), fp, deployed_by, now, completed)
