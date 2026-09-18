from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
from typing import Iterable, Mapping
import yaml

from src.listing_execution.operational_learning import OperationalImprovementCandidate


def _hash(payload: object) -> str:
    raw=json.dumps(payload,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode("utf-8")
    return sha256(raw).hexdigest()


def _validate_fp(value: str, label: str) -> None:
    if len(value)!=64 or any(c not in "0123456789abcdef" for c in value):
        raise ValueError(f"{label} must be lowercase sha256")


@dataclass(frozen=True)
class ExecutionPolicyVersion:
    version_id: str
    parent_version_id: str | None
    parent_fingerprint: str | None
    policy_values: tuple[tuple[str,bool],...]
    isolated_candidate: bool
    source_candidate_fingerprint: str | None
    policy_fingerprint: str


@dataclass(frozen=True)
class PolicyReplayFixture:
    fixture_id: str
    domain: str
    protected_control_expectations: tuple[str,...]
    fixture_fingerprint: str


@dataclass(frozen=True)
class PolicyReplayComparison:
    fixture_id: str
    domain: str
    changed_fields: tuple[str,...]
    protected_regressions: tuple[str,...]
    safety_regression: bool
    comparison_fingerprint: str


@dataclass(frozen=True)
class PolicyPromotionApproval:
    approval_id: str
    candidate_policy_fingerprint: str
    authority_id: str
    status: str
    approval_fingerprint: str


@dataclass(frozen=True)
class PolicyPromotionPackage:
    package_id: str
    candidate_version_id: str
    candidate_policy_fingerprint: str
    baseline_version_id: str
    baseline_policy_fingerprint: str
    rollback_version_id: str
    rollback_policy_fingerprint: str
    replay_root_fingerprint: str
    approval_id: str
    status: str
    public_eligible: bool
    external_action_capability: str
    package_fingerprint: str


@dataclass(frozen=True)
class PolicyCalibrationEvaluation:
    baseline: ExecutionPolicyVersion
    candidate: ExecutionPolicyVersion
    comparisons: tuple[PolicyReplayComparison,...]
    changed_fixture_count: int
    safety_regression_count: int
    approval_required: bool
    promotion_package: PolicyPromotionPackage | None
    evaluation_fingerprint: str


def load_policy_calibration_registry(path: str|Path) -> dict:
    raw=yaml.safe_load(Path(path).read_text())
    if raw.get("policy_calibration_registry_id")!="STH-M12-005-POLICY-CALIBRATION-v1.0":
        raise ValueError("unexpected M12-005 policy calibration registry id")
    if str(raw.get("version"))!="1.0.0" or raw.get("status")!="FROZEN":
        raise ValueError("M12-005 registry must be FROZEN v1.0")
    if raw.get("ticket")!="M12-005" or raw.get("parent_ticket")!="M12-004":
        raise ValueError("M12-005 registry lineage mismatch")
    return raw


def build_accepted_policy_baseline(registry: Mapping[str,object]) -> ExecutionPolicyVersion:
    values=tuple(sorted((str(k),bool(v)) for k,v in registry["policy_fields"].items()))
    payload={
        "version_id":registry["accepted_baseline"]["version"],
        "policy_values":values,
        "isolated_candidate":False,
    }
    return ExecutionPolicyVersion(
        version_id=str(registry["accepted_baseline"]["version"]),
        parent_version_id=None,
        parent_fingerprint=None,
        policy_values=values,
        isolated_candidate=False,
        source_candidate_fingerprint=None,
        policy_fingerprint=_hash(payload),
    )


def build_policy_fixture(
    *,
    fixture_id: str,
    domain: str,
    protected_control_expectations: Iterable[str],
    registry: Mapping[str,object],
) -> PolicyReplayFixture:
    if not fixture_id.strip():
        raise ValueError("fixture_id required")
    if domain not in set(registry["candidate_domains"]):
        raise ValueError("unsupported policy fixture domain")
    expectations=tuple(sorted(set(str(x) for x in protected_control_expectations)))
    allowed=set(registry["policy_fields"])
    if not expectations or not set(expectations).issubset(allowed):
        raise ValueError("fixture contains unsupported protected expectation")
    payload={
        "fixture_id":fixture_id,
        "domain":domain,
        "protected_control_expectations":expectations,
    }
    return PolicyReplayFixture(
        fixture_id=fixture_id,
        domain=domain,
        protected_control_expectations=expectations,
        fixture_fingerprint=_hash(payload),
    )


def build_policy_candidate(
    *,
    candidate_version_id: str,
    improvement_candidate: OperationalImprovementCandidate,
    domain: str,
    baseline: ExecutionPolicyVersion,
    policy_changes: Mapping[str,bool],
    registry: Mapping[str,object],
) -> ExecutionPolicyVersion:
    if improvement_candidate.advisory_only is not True or improvement_candidate.promotion_status!="NOT_PROMOTED":
        raise ValueError("M12-004 candidate must remain advisory and NOT_PROMOTED")
    if domain not in registry["candidate_domains"]:
        raise ValueError("unsupported calibration domain")
    allowed_types=set(registry["candidate_domains"][domain]["allowed_candidate_types"])
    if improvement_candidate.candidate_type not in allowed_types:
        raise ValueError("M12-004 candidate type is not eligible for selected domain")
    if not candidate_version_id.strip():
        raise ValueError("candidate_version_id required")
    if not policy_changes:
        raise ValueError("policy changes required")
    known=set(registry["policy_fields"])
    if not set(policy_changes).issubset(known):
        raise ValueError("candidate contains unsupported policy field")
    base=dict(baseline.policy_values)
    values=dict(base)
    for key,value in policy_changes.items():
        if not isinstance(value,bool):
            raise ValueError("policy change values must be bool")
        values[key]=value
    values_tuple=tuple(sorted(values.items()))
    payload={
        "version_id":candidate_version_id,
        "parent_version_id":baseline.version_id,
        "parent_fingerprint":baseline.policy_fingerprint,
        "source_candidate_fingerprint":improvement_candidate.candidate_fingerprint,
        "domain":domain,
        "policy_values":values_tuple,
        "isolated_candidate":True,
    }
    return ExecutionPolicyVersion(
        version_id=candidate_version_id,
        parent_version_id=baseline.version_id,
        parent_fingerprint=baseline.policy_fingerprint,
        policy_values=values_tuple,
        isolated_candidate=True,
        source_candidate_fingerprint=improvement_candidate.candidate_fingerprint,
        policy_fingerprint=_hash(payload),
    )


def make_policy_promotion_approval(
    *,
    approval_id: str,
    candidate_policy_fingerprint: str,
    authority_id: str,
    status: str,
) -> PolicyPromotionApproval:
    if status not in {"PENDING","APPROVED","REJECTED"}:
        raise ValueError("unsupported promotion approval status")
    if not approval_id.strip() or not authority_id.strip():
        raise ValueError("promotion approval id and authority id required")
    _validate_fp(candidate_policy_fingerprint,"candidate_policy_fingerprint")
    payload={
        "approval_id":approval_id,
        "candidate_policy_fingerprint":candidate_policy_fingerprint,
        "authority_id":authority_id,
        "status":status,
    }
    return PolicyPromotionApproval(
        approval_id=approval_id,
        candidate_policy_fingerprint=candidate_policy_fingerprint,
        authority_id=authority_id,
        status=status,
        approval_fingerprint=_hash(payload),
    )


def _compare(
    *,
    baseline: ExecutionPolicyVersion,
    candidate: ExecutionPolicyVersion,
    fixture: PolicyReplayFixture,
    registry: Mapping[str,object],
) -> PolicyReplayComparison:
    b=dict(baseline.policy_values)
    c=dict(candidate.policy_values)
    changed=tuple(sorted(k for k in b if b[k]!=c[k]))
    protected=set(registry["protected_true_fields"]) | set(fixture.protected_control_expectations)
    regressions=tuple(sorted(k for k in protected if b.get(k) is True and c.get(k) is not True))
    payload={
        "fixture_id":fixture.fixture_id,
        "domain":fixture.domain,
        "changed_fields":changed,
        "protected_regressions":regressions,
        "safety_regression":bool(regressions),
    }
    return PolicyReplayComparison(
        fixture_id=fixture.fixture_id,
        domain=fixture.domain,
        changed_fields=changed,
        protected_regressions=regressions,
        safety_regression=bool(regressions),
        comparison_fingerprint=_hash(payload),
    )


def evaluate_policy_candidate(
    *,
    baseline: ExecutionPolicyVersion,
    candidate: ExecutionPolicyVersion,
    fixtures: Iterable[PolicyReplayFixture],
    registry: Mapping[str,object],
    promotion_approval: PolicyPromotionApproval | None = None,
) -> PolicyCalibrationEvaluation:
    if candidate.isolated_candidate is not True:
        raise ValueError("candidate policy must be isolated")
    if candidate.parent_version_id!=baseline.version_id or candidate.parent_fingerprint!=baseline.policy_fingerprint:
        raise ValueError("candidate parent lineage mismatch")
    rows=tuple(fixtures)
    if not rows:
        raise ValueError("policy replay fixtures required")
    seen=set()
    comparisons=[]
    for fixture in rows:
        if fixture.fixture_id in seen:
            raise ValueError("duplicate policy replay fixture_id")
        seen.add(fixture.fixture_id)
        comparisons.append(_compare(baseline=baseline,candidate=candidate,fixture=fixture,registry=registry))
    comparisons=tuple(sorted(comparisons,key=lambda x:x.fixture_id))
    changed_count=sum(1 for x in comparisons if x.changed_fields)
    regression_count=sum(1 for x in comparisons if x.safety_regression)
    replay_root=_hash([x.comparison_fingerprint for x in comparisons])

    package=None
    if promotion_approval is not None:
        if promotion_approval.candidate_policy_fingerprint!=candidate.policy_fingerprint:
            raise ValueError("promotion approval candidate fingerprint mismatch")
        if promotion_approval.status=="APPROVED" and regression_count==0:
            payload={
                "package_id":f"PKG-{candidate.version_id}",
                "candidate_version_id":candidate.version_id,
                "candidate_policy_fingerprint":candidate.policy_fingerprint,
                "baseline_version_id":baseline.version_id,
                "baseline_policy_fingerprint":baseline.policy_fingerprint,
                "rollback_version_id":baseline.version_id,
                "rollback_policy_fingerprint":baseline.policy_fingerprint,
                "replay_root_fingerprint":replay_root,
                "approval_id":promotion_approval.approval_id,
                "status":registry["promotion"]["promotion_package_status"],
                "public_eligible":False,
                "external_action_capability":"NONE",
            }
            package=PolicyPromotionPackage(**payload,package_fingerprint=_hash(payload))

    payload={
        "baseline_policy_fingerprint":baseline.policy_fingerprint,
        "candidate_policy_fingerprint":candidate.policy_fingerprint,
        "comparisons":[x.comparison_fingerprint for x in comparisons],
        "changed_fixture_count":changed_count,
        "safety_regression_count":regression_count,
        "approval_fingerprint":promotion_approval.approval_fingerprint if promotion_approval else None,
        "promotion_package_fingerprint":package.package_fingerprint if package else None,
    }
    return PolicyCalibrationEvaluation(
        baseline=baseline,
        candidate=candidate,
        comparisons=comparisons,
        changed_fixture_count=changed_count,
        safety_regression_count=regression_count,
        approval_required=True,
        promotion_package=package,
        evaluation_fingerprint=_hash(payload),
    )
