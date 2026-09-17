from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from uuid import UUID, uuid4

import yaml

from src.production_certification.cohort.deployment import CohortDeployment
from src.production_certification.cohort.membership import FrozenCohortMembership
from src.shared.canonical_json import canonical_json


@dataclass(frozen=True)
class CohortEvidencePolicy:
    policy_version: str
    require_membership_fingerprint_match: bool
    require_candidate_fingerprint_match: bool
    require_approval_fingerprint_match: bool
    require_exact_item_count: bool
    require_all_items_pass: bool
    allowed_deployment_statuses: tuple[str, ...]

    @classmethod
    def load(cls, path: str | Path) -> "CohortEvidencePolicy":
        data = yaml.safe_load(Path(path).read_text())
        if data.get("status") != "LOCKED":
            raise ValueError("cohort evidence policy must be LOCKED")
        statuses = tuple(str(x) for x in (data.get("allowed_deployment_statuses") or ()))
        if not statuses:
            raise ValueError("cohort evidence policy requires allowed statuses")
        return cls(str(data["policy_version"]), bool(data.get("require_membership_fingerprint_match", True)),
            bool(data.get("require_candidate_fingerprint_match", True)), bool(data.get("require_approval_fingerprint_match", True)),
            bool(data.get("require_exact_item_count", True)), bool(data.get("require_all_items_pass", True)), statuses)


@dataclass(frozen=True)
class CohortEvidenceCertification:
    cohort_certification_id: UUID
    production_certification_id: UUID
    cohort_id: UUID
    cohort_deployment_id: UUID
    policy_version: str
    certification_status: str
    reason_codes: tuple[str, ...]
    expected_item_count: int
    deployed_item_count: int
    passed_item_count: int
    membership_fingerprint: str
    deployment_fingerprint: str
    certification_fingerprint: str
    certified_by: str


class CohortEvidenceCertifier:
    def certify(self, *, policy: CohortEvidencePolicy, membership: FrozenCohortMembership,
                deployment: CohortDeployment, certified_by: str,
                cohort_certification_id: UUID | None = None) -> CohortEvidenceCertification:
        if not certified_by.strip():
            raise ValueError("certified_by is required")
        reasons: list[str] = []
        if deployment.production_certification_id != membership.production_certification_id or deployment.cohort_id != membership.cohort_id:
            reasons.append("COHORT_IDENTITY_MISMATCH")
        if deployment.deployment_status not in policy.allowed_deployment_statuses:
            reasons.append("DEPLOYMENT_STATUS_NOT_ACCEPTED")
        if policy.require_membership_fingerprint_match and deployment.membership_fingerprint != membership.membership_fingerprint:
            reasons.append("MEMBERSHIP_FINGERPRINT_MISMATCH")
        if policy.require_candidate_fingerprint_match and deployment.candidate_fingerprint != membership.candidate_fingerprint:
            reasons.append("CANDIDATE_FINGERPRINT_MISMATCH")
        if policy.require_approval_fingerprint_match and deployment.limited_approval_fingerprint != membership.limited_approval_fingerprint:
            reasons.append("APPROVAL_FINGERPRINT_MISMATCH")
        expected = len(membership.property_ids)
        deployed = len(deployment.items)
        passed = sum(1 for x in deployment.items if x.status == "PASS")
        if policy.require_exact_item_count and deployed != expected:
            reasons.append("DEPLOYED_ITEM_COUNT_MISMATCH")
        if policy.require_all_items_pass and passed != expected:
            reasons.append("DEPLOYMENT_ITEM_FAILURE")
        status = "PASS" if not reasons else "FAIL"
        cid = cohort_certification_id or uuid4()
        payload = {
            "cohort_certification_id": str(cid), "production_certification_id": str(membership.production_certification_id),
            "cohort_id": str(membership.cohort_id), "cohort_deployment_id": str(deployment.cohort_deployment_id),
            "policy_version": policy.policy_version, "certification_status": status,
            "reason_codes": sorted(reasons), "expected_item_count": expected, "deployed_item_count": deployed,
            "passed_item_count": passed, "membership_fingerprint": membership.membership_fingerprint,
            "deployment_fingerprint": deployment.deployment_fingerprint,
        }
        fp = sha256(canonical_json(payload).encode("utf-8")).hexdigest()
        return CohortEvidenceCertification(cid, membership.production_certification_id, membership.cohort_id,
            deployment.cohort_deployment_id, policy.policy_version, status, tuple(sorted(reasons)), expected,
            deployed, passed, membership.membership_fingerprint, deployment.deployment_fingerprint, fp, certified_by)
