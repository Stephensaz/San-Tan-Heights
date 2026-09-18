from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
from typing import Iterable, Mapping
import yaml

from src.seller_intelligence.effectiveness import CalibrationCandidate


def _hash(payload: object) -> str:
    raw=json.dumps(payload,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode("utf-8")
    return sha256(raw).hexdigest()


def _validate_fp(value: str, label: str) -> None:
    if len(value)!=64 or any(c not in "0123456789abcdef" for c in value):
        raise ValueError(f"{label} must be lowercase sha256")


@dataclass(frozen=True)
class RuleVersion:
    version_id: str
    parent_version_id: str | None
    parent_fingerprint: str | None
    rules: tuple[tuple[str,bool],...]
    isolated_candidate: bool
    rule_fingerprint: str


@dataclass(frozen=True)
class HistoricalReplayFixture:
    fixture_id: str
    competitive_pressure: str
    buyer_depth: str
    pricing_response_environment: str
    new_construction_pressure: str
    verified_differentiation: str
    week_over_week_direction: str
    protected_behavior: bool
    fixture_fingerprint: str


@dataclass(frozen=True)
class ReplayComparison:
    fixture_id: str
    baseline_triggered_days: tuple[int,...]
    candidate_triggered_days: tuple[int,...]
    changed_days: tuple[int,...]
    communication_effect: str
    regression: bool
    regression_reasons: tuple[str,...]
    comparison_fingerprint: str


@dataclass(frozen=True)
class PromotionApproval:
    approval_id: str
    candidate_rule_fingerprint: str
    authority_id: str
    status: str
    approval_fingerprint: str


@dataclass(frozen=True)
class PromotionPackage:
    package_id: str
    candidate_version_id: str
    candidate_rule_fingerprint: str
    baseline_rule_fingerprint: str
    rollback_version_id: str
    rollback_rule_fingerprint: str
    approval_id: str
    replay_root_fingerprint: str
    status: str
    public_eligible: bool
    external_action_capability: str
    package_fingerprint: str


@dataclass(frozen=True)
class CalibrationEvaluation:
    baseline: RuleVersion
    candidate: RuleVersion
    comparisons: tuple[ReplayComparison,...]
    regression_count: int
    changed_fixture_count: int
    approval_required: bool
    promotion_package: PromotionPackage | None
    evaluation_fingerprint: str


def load_calibration_registry(path: str|Path) -> dict:
    raw=yaml.safe_load(Path(path).read_text())
    if raw.get("seller_calibration_registry_id")!="STH-M11-008-CALIBRATION-PROMOTION-v1.0":
        raise ValueError("unexpected M11-008 calibration registry id")
    if str(raw.get("version"))!="1.0.0" or raw.get("status")!="FROZEN":
        raise ValueError("M11-008 registry must be FROZEN v1.0")
    if raw.get("ticket")!="M11-008":
        raise ValueError("M11-008 registry ticket mismatch")
    return raw


def build_accepted_baseline(registry: Mapping[str,object]) -> RuleVersion:
    rules=tuple(sorted((str(k),bool(v)) for k,v in registry["accepted_rule_values"].items()))
    payload={
        "version_id":registry["accepted_baseline"]["version"],
        "rules":rules,
        "isolated_candidate":False,
    }
    return RuleVersion(
        version_id=str(registry["accepted_baseline"]["version"]),
        parent_version_id=None,
        parent_fingerprint=None,
        rules=rules,
        isolated_candidate=False,
        rule_fingerprint=_hash(payload),
    )


def build_fixture(
    *,
    fixture_id: str,
    competitive_pressure: str,
    buyer_depth: str,
    pricing_response_environment: str,
    new_construction_pressure: str,
    verified_differentiation: str,
    week_over_week_direction: str,
    protected_behavior: bool,
) -> HistoricalReplayFixture:
    if not fixture_id.strip():
        raise ValueError("fixture_id required")
    payload={
        "fixture_id":fixture_id,
        "competitive_pressure":competitive_pressure,
        "buyer_depth":buyer_depth,
        "pricing_response_environment":pricing_response_environment,
        "new_construction_pressure":new_construction_pressure,
        "verified_differentiation":verified_differentiation,
        "week_over_week_direction":week_over_week_direction,
        "protected_behavior":protected_behavior,
    }
    return HistoricalReplayFixture(
        fixture_id=fixture_id,
        competitive_pressure=competitive_pressure,
        buyer_depth=buyer_depth,
        pricing_response_environment=pricing_response_environment,
        new_construction_pressure=new_construction_pressure,
        verified_differentiation=verified_differentiation,
        week_over_week_direction=week_over_week_direction,
        protected_behavior=protected_behavior,
        fixture_fingerprint=_hash(payload),
    )


def build_candidate_version(
    *,
    candidate_id: str,
    advisory_candidate: CalibrationCandidate,
    baseline: RuleVersion,
    rule_changes: Mapping[str,bool],
    registry: Mapping[str,object],
) -> RuleVersion:
    if advisory_candidate.advisory_only is not True or advisory_candidate.promotion_status!="NOT_PROMOTED":
        raise ValueError("M11-007 calibration candidate must be advisory and not promoted")
    if advisory_candidate.candidate_type not in set(registry["allowed_candidate_types"]):
        raise ValueError("unsupported M11-007 calibration candidate type")
    if not candidate_id.strip():
        raise ValueError("candidate_id required")
    allowed=set(registry["rule_schema"])
    if not rule_changes:
        raise ValueError("candidate rule changes required")
    if not set(rule_changes).issubset(allowed):
        raise ValueError("candidate contains unsupported rule")
    base=dict(baseline.rules)
    candidate_rules=dict(base)
    for key,value in rule_changes.items():
        if not isinstance(value,bool):
            raise ValueError("candidate rule values must be bool")
        candidate_rules[key]=value
    rules=tuple(sorted(candidate_rules.items()))
    payload={
        "version_id":candidate_id,
        "parent_version_id":baseline.version_id,
        "parent_fingerprint":baseline.rule_fingerprint,
        "m11_007_candidate_fingerprint":advisory_candidate.candidate_fingerprint,
        "rules":rules,
        "isolated_candidate":True,
    }
    return RuleVersion(
        version_id=candidate_id,
        parent_version_id=baseline.version_id,
        parent_fingerprint=baseline.rule_fingerprint,
        rules=rules,
        isolated_candidate=True,
        rule_fingerprint=_hash(payload),
    )


def _triggered_days(version: RuleVersion, f: HistoricalReplayFixture) -> tuple[int,...]:
    rules=dict(version.rules)
    days=[]
    if (
        (rules["DAY_7_HIGH_PRESSURE_REVIEW_ENABLED"] and f.competitive_pressure=="HIGH")
        or (rules["DAY_7_THIN_BUYER_DEPTH_REVIEW_ENABLED"] and f.buyer_depth=="THIN")
        or (rules["DAY_7_WORSENING_DIRECTION_REVIEW_ENABLED"] and f.week_over_week_direction=="WORSENING")
    ):
        days.append(7)
    if (
        (rules["DAY_10_WEAK_RESPONSE_REVIEW_ENABLED"] and f.pricing_response_environment=="WEAK")
        or (rules["DAY_10_HIGH_NEW_CONSTRUCTION_REVIEW_ENABLED"] and f.new_construction_pressure=="HIGH")
        or (rules["DAY_10_LIMITED_DIFFERENTIATION_REVIEW_ENABLED"] and f.verified_differentiation=="LIMITED")
        or (rules["DAY_10_MIXED_RESPONSE_REVIEW_ENABLED"] and f.pricing_response_environment=="MIXED")
    ):
        days.append(10)
    if rules["DAY_14_ALWAYS_REVIEW_ENABLED"]:
        days.append(14)
    return tuple(days)


def _compare(
    baseline: RuleVersion,
    candidate: RuleVersion,
    fixture: HistoricalReplayFixture,
) -> ReplayComparison:
    b=_triggered_days(baseline,fixture)
    c=_triggered_days(candidate,fixture)
    changed=tuple(sorted(set(b)^set(c)))
    regression_reasons=[]
    if fixture.protected_behavior:
        lost=tuple(sorted(set(b)-set(c)))
        if lost:
            regression_reasons.append("PROTECTED_REVIEW_TRIGGER_REMOVED:"+",".join(map(str,lost)))
    if 14 not in c:
        regression_reasons.append("DAY_14_ALWAYS_REVIEW_REGRESSION")
    effect="UNCHANGED"
    if set(c)-set(b):
        effect="ADDED_REVIEW_GUIDANCE"
    elif set(b)-set(c):
        effect="REMOVED_REVIEW_GUIDANCE"
    payload={
        "fixture_id":fixture.fixture_id,
        "baseline_triggered_days":b,
        "candidate_triggered_days":c,
        "changed_days":changed,
        "communication_effect":effect,
        "regression_reasons":tuple(regression_reasons),
    }
    return ReplayComparison(
        fixture_id=fixture.fixture_id,
        baseline_triggered_days=b,
        candidate_triggered_days=c,
        changed_days=changed,
        communication_effect=effect,
        regression=bool(regression_reasons),
        regression_reasons=tuple(regression_reasons),
        comparison_fingerprint=_hash(payload),
    )


def make_promotion_approval(
    *,
    approval_id: str,
    candidate_rule_fingerprint: str,
    authority_id: str,
    status: str,
) -> PromotionApproval:
    if status not in {"APPROVED","REJECTED","PENDING"}:
        raise ValueError("unsupported promotion approval status")
    if not approval_id.strip() or not authority_id.strip():
        raise ValueError("promotion approval id and authority required")
    _validate_fp(candidate_rule_fingerprint,"candidate_rule_fingerprint")
    payload={
        "approval_id":approval_id,
        "candidate_rule_fingerprint":candidate_rule_fingerprint,
        "authority_id":authority_id,
        "status":status,
    }
    return PromotionApproval(
        approval_id=approval_id,
        candidate_rule_fingerprint=candidate_rule_fingerprint,
        authority_id=authority_id,
        status=status,
        approval_fingerprint=_hash(payload),
    )


def evaluate_candidate(
    *,
    baseline: RuleVersion,
    candidate: RuleVersion,
    fixtures: Iterable[HistoricalReplayFixture],
    registry: Mapping[str,object],
    approval: PromotionApproval | None = None,
) -> CalibrationEvaluation:
    if candidate.isolated_candidate is not True:
        raise ValueError("candidate must be isolated")
    if candidate.parent_version_id!=baseline.version_id or candidate.parent_fingerprint!=baseline.rule_fingerprint:
        raise ValueError("candidate parent lineage mismatch")
    rows=tuple(fixtures)
    if not rows:
        raise ValueError("historical replay fixtures required")
    seen=set()
    comparisons=[]
    for fixture in rows:
        if fixture.fixture_id in seen:
            raise ValueError("duplicate replay fixture_id")
        seen.add(fixture.fixture_id)
        comparisons.append(_compare(baseline,candidate,fixture))
    comparisons=tuple(sorted(comparisons,key=lambda x:x.fixture_id))
    regressions=sum(1 for x in comparisons if x.regression)
    changed=sum(1 for x in comparisons if x.changed_days)
    replay_root=_hash([x.comparison_fingerprint for x in comparisons])

    package=None
    if regressions==0 and approval is not None:
        if approval.candidate_rule_fingerprint!=candidate.rule_fingerprint:
            raise ValueError("promotion approval candidate fingerprint mismatch")
        if approval.status=="APPROVED":
            payload={
                "package_id":f"PKG-{candidate.version_id}",
                "candidate_version_id":candidate.version_id,
                "candidate_rule_fingerprint":candidate.rule_fingerprint,
                "baseline_rule_fingerprint":baseline.rule_fingerprint,
                "rollback_version_id":baseline.version_id,
                "rollback_rule_fingerprint":baseline.rule_fingerprint,
                "approval_id":approval.approval_id,
                "replay_root_fingerprint":replay_root,
                "status":registry["promotion"]["promotion_package_status"],
                "public_eligible":False,
                "external_action_capability":"NONE",
            }
            package=PromotionPackage(
                package_id=payload["package_id"],
                candidate_version_id=candidate.version_id,
                candidate_rule_fingerprint=candidate.rule_fingerprint,
                baseline_rule_fingerprint=baseline.rule_fingerprint,
                rollback_version_id=baseline.version_id,
                rollback_rule_fingerprint=baseline.rule_fingerprint,
                approval_id=approval.approval_id,
                replay_root_fingerprint=replay_root,
                status=payload["status"],
                public_eligible=False,
                external_action_capability="NONE",
                package_fingerprint=_hash(payload),
            )

    evaluation_payload={
        "baseline_fingerprint":baseline.rule_fingerprint,
        "candidate_fingerprint":candidate.rule_fingerprint,
        "comparisons":[x.comparison_fingerprint for x in comparisons],
        "regression_count":regressions,
        "changed_fixture_count":changed,
        "approval_fingerprint":approval.approval_fingerprint if approval else None,
        "promotion_package_fingerprint":package.package_fingerprint if package else None,
    }
    return CalibrationEvaluation(
        baseline=baseline,
        candidate=candidate,
        comparisons=comparisons,
        regression_count=regressions,
        changed_fixture_count=changed,
        approval_required=True,
        promotion_package=package,
        evaluation_fingerprint=_hash(evaluation_payload),
    )
