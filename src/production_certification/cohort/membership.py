from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Mapping
from uuid import UUID, uuid4

import yaml

from src.production_certification.approval.limited import LimitedApproval
from src.production_certification.pilot.eligibility import PilotEligibilityResult
from src.shared.canonical_json import canonical_json


@dataclass(frozen=True)
class CohortDefinition:
    cohort_code: str
    property_count: int
    approval_type: str
    selection_strategy: str
    require_exact_size: bool
    allowed_variants: tuple[str, ...]


@dataclass(frozen=True)
class CohortRegistry:
    registry_id: str
    registry_version: str
    cohorts: Mapping[str, CohortDefinition]

    @classmethod
    def load(cls, path: str | Path) -> "CohortRegistry":
        data = yaml.safe_load(Path(path).read_text())
        if data.get("status") != "LOCKED":
            raise ValueError("cohort registry must be LOCKED")
        raw = data.get("cohorts") or {}
        if not raw:
            raise ValueError("cohort registry requires cohorts")
        cohorts: dict[str, CohortDefinition] = {}
        for code, row in raw.items():
            count = int(row.get("property_count", 0))
            variants = tuple(str(x) for x in (row.get("allowed_variants") or ()))
            if count < 1 or not variants:
                raise ValueError(f"invalid cohort definition: {code}")
            cohorts[str(code)] = CohortDefinition(
                str(code), count, str(row["approval_type"]), str(row["selection_strategy"]),
                bool(row.get("require_exact_size", True)), variants,
            )
        return cls(str(data["registry_id"]), str(data["registry_version"]), cohorts)

    def require(self, cohort_code: str) -> CohortDefinition:
        try:
            return self.cohorts[cohort_code]
        except KeyError as exc:
            raise ValueError(f"unknown cohort code: {cohort_code}") from exc


@dataclass(frozen=True)
class FrozenCohortMembership:
    cohort_id: UUID
    production_certification_id: UUID
    cohort_code: str
    policy_version: str
    candidate_fingerprint: str
    pilot_membership_fingerprint: str
    limited_approval_id: UUID
    limited_approval_fingerprint: str
    property_ids: tuple[UUID, ...]
    allowed_variants: tuple[str, ...]
    membership_fingerprint: str
    frozen_by: str
    frozen_at: datetime


class CohortMembershipFreezer:
    def freeze(
        self,
        *,
        registry: CohortRegistry,
        cohort_code: str,
        pilot: PilotEligibilityResult,
        approval: LimitedApproval,
        candidate_fingerprint: str,
        frozen_by: str,
        frozen_at: datetime | None = None,
        cohort_id: UUID | None = None,
    ) -> FrozenCohortMembership:
        if not frozen_by.strip():
            raise ValueError("frozen_by is required")
        definition = registry.require(cohort_code)
        if approval.approval_type != definition.approval_type:
            raise ValueError("approval type does not authorize cohort")
        if approval.candidate_fingerprint != candidate_fingerprint:
            raise ValueError("candidate fingerprint mismatch")
        if approval.pilot_membership_fingerprint != pilot.membership_fingerprint:
            raise ValueError("pilot membership fingerprint mismatch")
        now = frozen_at or datetime.now(timezone.utc)
        if now.tzinfo is None:
            raise ValueError("frozen_at must be timezone-aware")
        if not (approval.issued_at <= now < approval.expires_at):
            raise ValueError("limited approval is not active")
        if definition.property_count > approval.max_properties:
            raise ValueError("cohort exceeds limited approval property cap")
        if not set(definition.allowed_variants).issubset(set(approval.allowed_variants)):
            raise ValueError("cohort variant exceeds limited approval scope")
        selected = tuple(pilot.selected_property_ids[: definition.property_count])
        if definition.require_exact_size and len(selected) != definition.property_count:
            raise ValueError("insufficient eligible pilot properties for exact cohort")
        cid = cohort_id or uuid4()
        payload = {
            "cohort_id": str(cid),
            "production_certification_id": str(approval.production_certification_id),
            "cohort_code": cohort_code,
            "policy_version": registry.registry_version,
            "candidate_fingerprint": candidate_fingerprint,
            "pilot_membership_fingerprint": pilot.membership_fingerprint,
            "limited_approval_id": str(approval.limited_approval_id),
            "limited_approval_fingerprint": approval.approval_fingerprint,
            "property_ids": [str(x) for x in selected],
            "allowed_variants": list(definition.allowed_variants),
        }
        fp = sha256(canonical_json(payload).encode("utf-8")).hexdigest()
        return FrozenCohortMembership(
            cid, approval.production_certification_id, cohort_code, registry.registry_version,
            candidate_fingerprint, pilot.membership_fingerprint, approval.limited_approval_id,
            approval.approval_fingerprint, selected, definition.allowed_variants, fp, frozen_by, now,
        )
