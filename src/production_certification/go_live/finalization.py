from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any, Iterable, Mapping, Protocol
from uuid import UUID, uuid4
import re
import yaml

from src.production_certification.go_live.publication_control import RollbackBaseline, RollbackBaselineEntry
from src.production_certification.go_live.stop_conditions import GoLiveStopResult
from src.shared.canonical_json import canonical_json

_SHA256 = re.compile(r"^[0-9a-f]{64}$")


def _hash(payload: Mapping[str, Any]) -> str:
    return sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def _require_hash(value: str, name: str) -> None:
    if not _SHA256.fullmatch(value):
        raise ValueError(f"{name} must be lowercase sha256")


class RollbackPointerExecutor(Protocol):
    def restore(self, *, entry: RollbackBaselineEntry) -> Mapping[str, Any]: ...
    def contain(self, *, property_id: UUID, reason_code: str) -> Mapping[str, Any]: ...


@dataclass(frozen=True)
class RollbackContainmentItem:
    property_id: UUID
    variant: str
    channel: str
    status: str
    evidence_hash: str
    detail: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RollbackContainmentRun:
    rollback_run_id: UUID
    production_certification_id: UUID
    stage_code: str
    candidate_fingerprint: str
    rollback_baseline_id: UUID
    rollback_baseline_fingerprint: str
    status: str
    items: tuple[RollbackContainmentItem, ...]
    run_fingerprint: str
    executed_by: str
    reason_code: str
    executed_at: datetime


class CohortRollbackContainmentService:
    def execute(self, *, baseline: RollbackBaseline, candidate_fingerprint: str,
                executor: RollbackPointerExecutor, executed_by: str, reason_code: str,
                rollback_run_id: UUID | None = None, executed_at: datetime | None = None) -> RollbackContainmentRun:
        if baseline.candidate_fingerprint != candidate_fingerprint:
            raise ValueError("rollback candidate fingerprint mismatch")
        if not executed_by.strip() or not reason_code.strip():
            raise ValueError("executed_by and reason_code are required")
        now = executed_at or datetime.now(timezone.utc)
        if now.tzinfo is None:
            raise ValueError("executed_at must be timezone-aware")
        items: list[RollbackContainmentItem] = []
        # Reverse deterministic order minimizes forward rollout exposure during rollback.
        for entry in reversed(baseline.entries):
            detail: dict[str, Any]
            try:
                detail = dict(executor.restore(entry=entry))
                status = "PASS"
            except Exception as exc:
                containment = dict(executor.contain(property_id=entry.property_id, reason_code=reason_code))
                detail = {"error_type": exc.__class__.__name__, "error": str(exc), "containment": containment}
                status = "CONTAINED"
            ep = {
                "property_id": str(entry.property_id), "variant": entry.variant, "channel": entry.channel,
                "status": status, "detail": detail, "baseline_entry_fingerprint": entry.entry_fingerprint,
            }
            items.append(RollbackContainmentItem(entry.property_id, entry.variant, entry.channel, status, _hash(ep), detail))
        status = "PASS" if all(x.status == "PASS" for x in items) else "CONTAINED"
        rid = rollback_run_id or uuid4()
        payload = {
            "rollback_run_id": str(rid), "production_certification_id": str(baseline.production_certification_id),
            "stage_code": baseline.stage_code, "candidate_fingerprint": candidate_fingerprint,
            "rollback_baseline_id": str(baseline.rollback_baseline_id),
            "rollback_baseline_fingerprint": baseline.baseline_fingerprint, "status": status,
            "item_evidence_hashes": [x.evidence_hash for x in items], "reason_code": reason_code,
        }
        return RollbackContainmentRun(rid, baseline.production_certification_id, baseline.stage_code,
            candidate_fingerprint, baseline.rollback_baseline_id, baseline.baseline_fingerprint, status,
            tuple(items), _hash(payload), executed_by, reason_code, now)


@dataclass(frozen=True)
class CertificationEvidenceItem:
    evidence_code: str
    evidence_fingerprint: str
    status: str = "PASS"

    def __post_init__(self) -> None:
        _require_hash(self.evidence_fingerprint, "evidence_fingerprint")


@dataclass(frozen=True)
class CertificationEvidenceBundle:
    evidence_bundle_id: UUID
    production_certification_id: UUID
    candidate_fingerprint: str
    required_codes: tuple[str, ...]
    items: tuple[CertificationEvidenceItem, ...]
    status: str
    bundle_fingerprint: str
    built_by: str
    built_at: datetime


class CertificationEvidenceBundleBuilder:
    def build(self, *, production_certification_id: UUID, candidate_fingerprint: str,
              required_codes: Iterable[str], items: Iterable[CertificationEvidenceItem], built_by: str,
              evidence_bundle_id: UUID | None = None, built_at: datetime | None = None) -> CertificationEvidenceBundle:
        _require_hash(candidate_fingerprint, "candidate_fingerprint")
        if not built_by.strip():
            raise ValueError("built_by is required")
        required = tuple(sorted(set(str(x) for x in required_codes)))
        rows = tuple(sorted(items, key=lambda x: x.evidence_code))
        if len({x.evidence_code for x in rows}) != len(rows):
            raise ValueError("duplicate certification evidence code")
        by_code = {x.evidence_code: x for x in rows}
        missing = [x for x in required if x not in by_code]
        if missing:
            raise ValueError(f"missing required certification evidence: {missing}")
        if any(by_code[x].status != "PASS" for x in required):
            raise ValueError("required certification evidence has not passed")
        now = built_at or datetime.now(timezone.utc)
        if now.tzinfo is None:
            raise ValueError("built_at must be timezone-aware")
        bid = evidence_bundle_id or uuid4()
        payload = {"evidence_bundle_id": str(bid), "production_certification_id": str(production_certification_id),
                   "candidate_fingerprint": candidate_fingerprint, "required_codes": list(required),
                   "items": [{"code": x.evidence_code, "fingerprint": x.evidence_fingerprint, "status": x.status} for x in rows]}
        return CertificationEvidenceBundle(bid, production_certification_id, candidate_fingerprint, required, rows,
                                           "PASS", _hash(payload), built_by, now)


@dataclass(frozen=True)
class CertificationRevocation:
    revocation_id: UUID
    production_certification_id: UUID
    candidate_fingerprint: str
    evidence_bundle_id: UUID
    evidence_bundle_fingerprint: str
    reason_code: str
    detail: str
    revoked_by: str
    revocation_fingerprint: str
    revoked_at: datetime


class CertificationRevocationService:
    def revoke(self, *, bundle: CertificationEvidenceBundle, candidate_fingerprint: str,
               reason_code: str, detail: str, revoked_by: str,
               revocation_id: UUID | None = None, revoked_at: datetime | None = None) -> CertificationRevocation:
        if bundle.candidate_fingerprint != candidate_fingerprint:
            raise ValueError("revocation candidate mismatch")
        if not reason_code.strip() or not detail.strip() or not revoked_by.strip():
            raise ValueError("reason_code, detail, and revoked_by are required")
        now = revoked_at or datetime.now(timezone.utc)
        if now.tzinfo is None:
            raise ValueError("revoked_at must be timezone-aware")
        rid = revocation_id or uuid4()
        payload = {"revocation_id": str(rid), "production_certification_id": str(bundle.production_certification_id),
                   "candidate_fingerprint": candidate_fingerprint, "evidence_bundle_id": str(bundle.evidence_bundle_id),
                   "evidence_bundle_fingerprint": bundle.bundle_fingerprint, "reason_code": reason_code,
                   "detail": detail, "revoked_by": revoked_by, "revoked_at": now.isoformat()}
        return CertificationRevocation(rid, bundle.production_certification_id, candidate_fingerprint,
            bundle.evidence_bundle_id, bundle.bundle_fingerprint, reason_code, detail, revoked_by, _hash(payload), now)


@dataclass(frozen=True)
class FullApprovalPolicy:
    policy_version: str
    approval_type: str
    required_evidence_codes: tuple[str, ...]
    required_rollout_stages: tuple[str, ...]
    requires_stop_condition_clearance: bool
    prohibits_active_revocation: bool

    @classmethod
    def load(cls, path: str | Path) -> "FullApprovalPolicy":
        data = yaml.safe_load(Path(path).read_text())
        if data.get("status") != "LOCKED" or data.get("approval_type") != "FULL_APPROVAL":
            raise ValueError("full approval policy must be LOCKED/FULL_APPROVAL")
        evidence = tuple(str(x) for x in (data.get("required_evidence_codes") or ()))
        stages = tuple(str(x) for x in (data.get("required_rollout_stages") or ()))
        if not evidence or not stages:
            raise ValueError("full approval policy requires evidence codes and rollout stages")
        return cls(str(data["policy_version"]), "FULL_APPROVAL", evidence, stages,
                   bool(data.get("requires_stop_condition_clearance", True)),
                   bool(data.get("prohibits_active_revocation", True)))


@dataclass(frozen=True)
class FullApproval:
    full_approval_id: UUID
    production_certification_id: UUID
    policy_version: str
    candidate_fingerprint: str
    evidence_bundle_id: UUID
    evidence_bundle_fingerprint: str
    stop_condition_fingerprint: str
    rollout_stage_certification_fingerprints: Mapping[str, str]
    approval_fingerprint: str
    approved_by: str
    approved_at: datetime
    approval_type: str = "FULL_APPROVAL"


class FullApprovalIssuer:
    def issue(self, *, policy: FullApprovalPolicy, bundle: CertificationEvidenceBundle,
              candidate_fingerprint: str, stop_conditions: GoLiveStopResult,
              rollout_stage_certifications: Mapping[str, tuple[str, str]], active_revocations: Iterable[CertificationRevocation],
              approved_by: str, full_approval_id: UUID | None = None, approved_at: datetime | None = None) -> FullApproval:
        if bundle.status != "PASS" or bundle.candidate_fingerprint != candidate_fingerprint:
            raise ValueError("certification evidence bundle is not valid for candidate")
        if bundle.production_certification_id != stop_conditions.production_certification_id:
            raise ValueError("stop-condition certification identity mismatch")
        if policy.requires_stop_condition_clearance and stop_conditions.status != "CLEAR":
            raise ValueError("go-live stop conditions are not clear")
        missing_evidence = sorted(set(policy.required_evidence_codes) - set(bundle.required_codes))
        if missing_evidence:
            raise ValueError(f"evidence bundle missing policy requirements: {missing_evidence}")
        certs: dict[str, str] = {}
        for stage in policy.required_rollout_stages:
            if stage not in rollout_stage_certifications:
                raise ValueError(f"missing rollout certification: {stage}")
            status, fingerprint = rollout_stage_certifications[stage]
            if status != "PASS":
                raise ValueError(f"rollout certification has not passed: {stage}")
            _require_hash(fingerprint, f"{stage}_fingerprint")
            certs[stage] = fingerprint
        if policy.prohibits_active_revocation:
            for rev in active_revocations:
                if rev.production_certification_id == bundle.production_certification_id and rev.candidate_fingerprint == candidate_fingerprint:
                    raise ValueError("candidate certification is revoked")
        if not approved_by.strip():
            raise ValueError("approved_by is required")
        now = approved_at or datetime.now(timezone.utc)
        if now.tzinfo is None:
            raise ValueError("approved_at must be timezone-aware")
        aid = full_approval_id or uuid4()
        payload = {"full_approval_id": str(aid), "production_certification_id": str(bundle.production_certification_id),
                   "policy_version": policy.policy_version, "approval_type": "FULL_APPROVAL",
                   "candidate_fingerprint": candidate_fingerprint, "evidence_bundle_id": str(bundle.evidence_bundle_id),
                   "evidence_bundle_fingerprint": bundle.bundle_fingerprint,
                   "stop_condition_fingerprint": stop_conditions.evidence_fingerprint,
                   "rollout_stage_certification_fingerprints": certs, "approved_by": approved_by,
                   "approved_at": now.isoformat()}
        return FullApproval(aid, bundle.production_certification_id, policy.policy_version, candidate_fingerprint,
                            bundle.evidence_bundle_id, bundle.bundle_fingerprint, stop_conditions.evidence_fingerprint,
                            certs, _hash(payload), approved_by, now)
