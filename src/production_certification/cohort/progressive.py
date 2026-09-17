from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any, Iterable, Mapping, Protocol
from uuid import UUID, uuid4

import yaml

from src.production_certification.cohort.certification import CohortEvidenceCertification
from src.production_certification.cohort.membership import FrozenCohortMembership
from src.production_certification.go_live.stop_conditions import GoLiveStopResult
from src.shared.canonical_json import canonical_json


@dataclass(frozen=True)
class ProgressiveStage:
    cohort_code: str
    property_count: int | None
    prior_cohort_code: str
    require_exact_size: bool


@dataclass(frozen=True)
class ProgressiveRolloutPolicy:
    registry_id: str
    registry_version: str
    requires_stop_condition_clearance: bool
    requires_prior_cohort_certification_pass: bool
    allowed_variants: tuple[str, ...]
    stages: Mapping[str, ProgressiveStage]

    @classmethod
    def load(cls, path: str | Path) -> "ProgressiveRolloutPolicy":
        data = yaml.safe_load(Path(path).read_text())
        if data.get("status") != "LOCKED":
            raise ValueError("progressive rollout policy must be LOCKED")
        if data.get("selection_order") != "PROPERTY_ID_ASC":
            raise ValueError("unsupported progressive rollout selection order")
        variants = tuple(str(x) for x in (data.get("allowed_variants") or ()))
        if not variants:
            raise ValueError("progressive rollout policy requires variants")
        stages: dict[str, ProgressiveStage] = {}
        for code, row in (data.get("stages") or {}).items():
            raw_count = row.get("property_count")
            count = None if raw_count == "ALL_REMAINING" else int(raw_count)
            if count is not None and count < 1:
                raise ValueError(f"invalid stage property_count: {code}")
            stages[str(code)] = ProgressiveStage(
                str(code), count, str(row["prior_cohort_code"]), bool(row.get("require_exact_size", True))
            )
        if not stages:
            raise ValueError("progressive rollout policy requires stages")
        return cls(
            str(data["registry_id"]), str(data["registry_version"]),
            bool(data.get("requires_stop_condition_clearance", True)),
            bool(data.get("requires_prior_cohort_certification_pass", True)),
            variants, stages,
        )

    def require_stage(self, cohort_code: str) -> ProgressiveStage:
        try:
            return self.stages[cohort_code]
        except KeyError as exc:
            raise ValueError(f"unknown progressive cohort: {cohort_code}") from exc


@dataclass(frozen=True)
class ProgressiveCohortMembership:
    cohort_id: UUID
    production_certification_id: UUID
    cohort_code: str
    policy_version: str
    candidate_fingerprint: str
    prior_cohort_code: str
    prior_cohort_certification_id: UUID
    prior_cohort_certification_fingerprint: str
    fleet_eligibility_fingerprint: str
    property_ids: tuple[UUID, ...]
    excluded_prior_property_ids: tuple[UUID, ...]
    allowed_variants: tuple[str, ...]
    membership_fingerprint: str
    frozen_by: str
    frozen_at: datetime


class ProgressiveCohortMembershipFreezer:
    def freeze(
        self,
        *,
        policy: ProgressiveRolloutPolicy,
        cohort_code: str,
        production_certification_id: UUID,
        candidate_fingerprint: str,
        fleet_eligibility_fingerprint: str,
        eligible_property_ids: Iterable[UUID],
        prior_memberships: Iterable[FrozenCohortMembership | ProgressiveCohortMembership],
        prior_certification: CohortEvidenceCertification,
        current_stop_conditions: GoLiveStopResult,
        frozen_by: str,
        frozen_at: datetime | None = None,
        cohort_id: UUID | None = None,
    ) -> ProgressiveCohortMembership:
        if not frozen_by.strip():
            raise ValueError("frozen_by is required")
        if len(candidate_fingerprint) != 64 or len(fleet_eligibility_fingerprint) != 64:
            raise ValueError("candidate and fleet eligibility fingerprints must be sha256")
        stage = policy.require_stage(cohort_code)
        prior_rows = tuple(prior_memberships)
        matching_prior = [x for x in prior_rows if x.cohort_code == stage.prior_cohort_code]
        if len(matching_prior) != 1:
            raise ValueError("exactly one immediate prior cohort membership is required")
        immediate = matching_prior[0]
        if immediate.production_certification_id != production_certification_id:
            raise ValueError("prior cohort certification identity mismatch")
        if immediate.candidate_fingerprint != candidate_fingerprint:
            raise ValueError("prior cohort candidate fingerprint mismatch")
        if policy.requires_prior_cohort_certification_pass:
            if prior_certification.certification_status != "PASS":
                raise ValueError("prior cohort certification has not passed")
            if prior_certification.production_certification_id != production_certification_id:
                raise ValueError("prior certification identity mismatch")
            if prior_certification.cohort_id != immediate.cohort_id:
                raise ValueError("prior certification does not certify immediate prior cohort")
            if prior_certification.membership_fingerprint != immediate.membership_fingerprint:
                raise ValueError("prior certification membership fingerprint mismatch")
        if policy.requires_stop_condition_clearance:
            if current_stop_conditions.production_certification_id != production_certification_id or current_stop_conditions.status != "CLEAR":
                raise ValueError("go-live stop conditions are not clear")
        raw_eligible = tuple(eligible_property_ids)
        if len(set(raw_eligible)) != len(raw_eligible):
            raise ValueError("duplicate eligible property IDs")
        eligible = tuple(sorted(raw_eligible, key=str))
        excluded = tuple(sorted({p for m in prior_rows for p in m.property_ids}, key=str))
        remaining = tuple(p for p in eligible if p not in set(excluded))
        selected = remaining if stage.property_count is None else remaining[: stage.property_count]
        if stage.require_exact_size and len(selected) != stage.property_count:
            raise ValueError("insufficient eligible properties for exact progressive cohort")
        if not selected:
            raise ValueError("progressive cohort cannot be empty")
        now = frozen_at or datetime.now(timezone.utc)
        if now.tzinfo is None:
            raise ValueError("frozen_at must be timezone-aware")
        cid = cohort_id or uuid4()
        payload = {
            "cohort_id": str(cid),
            "production_certification_id": str(production_certification_id),
            "cohort_code": cohort_code,
            "policy_version": policy.registry_version,
            "candidate_fingerprint": candidate_fingerprint,
            "prior_cohort_code": stage.prior_cohort_code,
            "prior_cohort_certification_id": str(prior_certification.cohort_certification_id),
            "prior_cohort_certification_fingerprint": prior_certification.certification_fingerprint,
            "fleet_eligibility_fingerprint": fleet_eligibility_fingerprint,
            "property_ids": [str(x) for x in selected],
            "excluded_prior_property_ids": [str(x) for x in excluded],
            "allowed_variants": list(policy.allowed_variants),
        }
        fp = sha256(canonical_json(payload).encode("utf-8")).hexdigest()
        return ProgressiveCohortMembership(
            cid, production_certification_id, cohort_code, policy.registry_version, candidate_fingerprint,
            stage.prior_cohort_code, prior_certification.cohort_certification_id,
            prior_certification.certification_fingerprint, fleet_eligibility_fingerprint,
            selected, excluded, policy.allowed_variants, fp, frozen_by, now,
        )


class ProgressiveDeploymentExecutor(Protocol):
    def deploy(self, *, property_id: UUID, variants: tuple[str, ...], candidate_fingerprint: str) -> Mapping[str, Any]: ...


@dataclass(frozen=True)
class ProgressiveDeploymentItem:
    property_id: UUID
    membership_ordinal: int
    status: str
    evidence_hash: str
    detail: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ProgressiveCohortDeployment:
    cohort_deployment_id: UUID
    cohort_id: UUID
    production_certification_id: UUID
    cohort_code: str
    candidate_fingerprint: str
    prior_cohort_certification_fingerprint: str
    membership_fingerprint: str
    deployment_status: str
    items: tuple[ProgressiveDeploymentItem, ...]
    deployment_fingerprint: str
    deployed_by: str
    started_at: datetime
    completed_at: datetime


class ProgressiveCohortDeploymentService:
    def deploy(
        self,
        *,
        membership: ProgressiveCohortMembership,
        prior_certification: CohortEvidenceCertification,
        current_stop_conditions: GoLiveStopResult,
        executor: ProgressiveDeploymentExecutor,
        deployed_by: str,
        started_at: datetime | None = None,
        deployment_id: UUID | None = None,
    ) -> ProgressiveCohortDeployment:
        if not deployed_by.strip():
            raise ValueError("deployed_by is required")
        if prior_certification.certification_status != "PASS":
            raise ValueError("prior cohort certification has not passed")
        if prior_certification.cohort_certification_id != membership.prior_cohort_certification_id:
            raise ValueError("prior certification ID mismatch")
        if prior_certification.certification_fingerprint != membership.prior_cohort_certification_fingerprint:
            raise ValueError("prior certification fingerprint mismatch")
        if current_stop_conditions.production_certification_id != membership.production_certification_id or current_stop_conditions.status != "CLEAR":
            raise ValueError("go-live stop conditions are not clear")
        now = started_at or datetime.now(timezone.utc)
        if now.tzinfo is None:
            raise ValueError("started_at must be timezone-aware")
        items: list[ProgressiveDeploymentItem] = []
        for ordinal, property_id in enumerate(membership.property_ids, start=1):
            try:
                detail = dict(executor.deploy(property_id=property_id, variants=membership.allowed_variants,
                                              candidate_fingerprint=membership.candidate_fingerprint))
                status = "PASS"
            except Exception as exc:
                detail = {"error_type": exc.__class__.__name__, "error": str(exc)}
                status = "FAIL"
            evidence_payload = {"property_id": str(property_id), "membership_ordinal": ordinal,
                                "status": status, "detail": detail}
            evidence_hash = sha256(canonical_json(evidence_payload).encode("utf-8")).hexdigest()
            items.append(ProgressiveDeploymentItem(property_id, ordinal, status, evidence_hash, detail))
            if status == "FAIL":
                break
        status = "PASS" if len(items) == len(membership.property_ids) and all(x.status == "PASS" for x in items) else "FAIL"
        did = deployment_id or uuid4()
        completed = datetime.now(timezone.utc)
        payload = {
            "cohort_deployment_id": str(did), "cohort_id": str(membership.cohort_id),
            "production_certification_id": str(membership.production_certification_id), "cohort_code": membership.cohort_code,
            "candidate_fingerprint": membership.candidate_fingerprint,
            "prior_cohort_certification_fingerprint": membership.prior_cohort_certification_fingerprint,
            "membership_fingerprint": membership.membership_fingerprint, "deployment_status": status,
            "item_evidence_hashes": [x.evidence_hash for x in items],
        }
        fp = sha256(canonical_json(payload).encode("utf-8")).hexdigest()
        return ProgressiveCohortDeployment(
            did, membership.cohort_id, membership.production_certification_id, membership.cohort_code,
            membership.candidate_fingerprint, membership.prior_cohort_certification_fingerprint,
            membership.membership_fingerprint, status, tuple(items), fp, deployed_by, now, completed,
        )


@dataclass(frozen=True)
class ProgressiveCohortCertification:
    cohort_certification_id: UUID
    production_certification_id: UUID
    cohort_id: UUID
    cohort_code: str
    cohort_deployment_id: UUID
    certification_status: str
    reason_codes: tuple[str, ...]
    expected_item_count: int
    deployed_item_count: int
    passed_item_count: int
    membership_fingerprint: str
    deployment_fingerprint: str
    certification_fingerprint: str
    certified_by: str


class ProgressiveCohortEvidenceCertifier:
    def certify(self, *, membership: ProgressiveCohortMembership, deployment: ProgressiveCohortDeployment,
                certified_by: str, cohort_certification_id: UUID | None = None) -> ProgressiveCohortCertification:
        if not certified_by.strip():
            raise ValueError("certified_by is required")
        reasons: list[str] = []
        if deployment.production_certification_id != membership.production_certification_id or deployment.cohort_id != membership.cohort_id:
            reasons.append("COHORT_IDENTITY_MISMATCH")
        if deployment.cohort_code != membership.cohort_code:
            reasons.append("COHORT_CODE_MISMATCH")
        if deployment.candidate_fingerprint != membership.candidate_fingerprint:
            reasons.append("CANDIDATE_FINGERPRINT_MISMATCH")
        if deployment.prior_cohort_certification_fingerprint != membership.prior_cohort_certification_fingerprint:
            reasons.append("PRIOR_CERTIFICATION_FINGERPRINT_MISMATCH")
        if deployment.membership_fingerprint != membership.membership_fingerprint:
            reasons.append("MEMBERSHIP_FINGERPRINT_MISMATCH")
        expected = len(membership.property_ids)
        deployed = len(deployment.items)
        passed = sum(1 for x in deployment.items if x.status == "PASS")
        if deployment.deployment_status != "PASS": reasons.append("DEPLOYMENT_STATUS_NOT_ACCEPTED")
        if deployed != expected: reasons.append("DEPLOYED_ITEM_COUNT_MISMATCH")
        if passed != expected: reasons.append("DEPLOYMENT_ITEM_FAILURE")
        status = "PASS" if not reasons else "FAIL"
        cid = cohort_certification_id or uuid4()
        payload = {
            "cohort_certification_id": str(cid), "production_certification_id": str(membership.production_certification_id),
            "cohort_id": str(membership.cohort_id), "cohort_code": membership.cohort_code,
            "cohort_deployment_id": str(deployment.cohort_deployment_id), "certification_status": status,
            "reason_codes": sorted(reasons), "expected_item_count": expected, "deployed_item_count": deployed,
            "passed_item_count": passed, "membership_fingerprint": membership.membership_fingerprint,
            "deployment_fingerprint": deployment.deployment_fingerprint,
        }
        fp = sha256(canonical_json(payload).encode("utf-8")).hexdigest()
        return ProgressiveCohortCertification(
            cid, membership.production_certification_id, membership.cohort_id, membership.cohort_code,
            deployment.cohort_deployment_id, status, tuple(sorted(reasons)), expected, deployed, passed,
            membership.membership_fingerprint, deployment.deployment_fingerprint, fp, certified_by,
        )
