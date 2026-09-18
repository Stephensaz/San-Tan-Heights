from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from hashlib import sha256
import json
from pathlib import Path
from typing import Iterable, Mapping
import yaml

from src.seller_intelligence.opportunity import SellerOpportunityResult
from src.seller_intelligence.strategy import PropertySellerStrategy
from src.seller_intelligence.scenario import ScenarioSensitivityResult
from src.seller_intelligence.timeline import SellerDecisionTimeline
from src.seller_intelligence.communication import SellerCommunicationProjection


def _hash(payload: object) -> str:
    raw=json.dumps(payload,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode("utf-8")
    return sha256(raw).hexdigest()


def _validate_fp(value: str, label: str) -> None:
    if len(value)!=64 or any(c not in "0123456789abcdef" for c in value):
        raise ValueError(f"{label} must be lowercase sha256")


def _parse_ts(value: str) -> datetime:
    try:
        dt=datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("human decision timestamp must be ISO-8601") from exc
    if dt.tzinfo is None:
        raise ValueError("human decision timestamp must include timezone")
    return dt


@dataclass(frozen=True)
class HumanDecision:
    decision_id: str
    review_item_id: str | None
    decision_type: str
    actor_id: str
    decided_at: str
    rationale: str
    decision_fingerprint: str


@dataclass(frozen=True)
class ReviewItem:
    review_item_id: str
    source_event_fingerprint: str
    snapshot_id: str
    status: str
    reasons: tuple[str,...]
    acknowledged_by_decision_id: str | None
    resolved_by_decision_id: str | None
    review_item_fingerprint: str


@dataclass(frozen=True)
class ArtifactRef:
    artifact_type: str
    artifact_fingerprint: str
    status: str
    artifact_ref_fingerprint: str


@dataclass(frozen=True)
class SellerIntelligenceCase:
    case_id: str
    subject_property_id: str
    current_artifacts: tuple[ArtifactRef,...]
    superseded_artifacts: tuple[ArtifactRef,...]
    review_items: tuple[ReviewItem,...]
    human_decisions: tuple[HumanDecision,...]
    limitations: tuple[str,...]
    next_safe_step: str
    output_tier: str
    public_eligible: bool
    external_action_capability: str
    case_fingerprint: str


def load_workspace_registry(path: str|Path) -> dict:
    raw=yaml.safe_load(Path(path).read_text())
    if raw.get("seller_workspace_registry_id")!="STH-M11-006-SELLER-WORKSPACE-v1.0":
        raise ValueError("unexpected M11-006 workspace registry id")
    if str(raw.get("version"))!="1.0.0" or raw.get("status")!="FROZEN":
        raise ValueError("M11-006 registry must be FROZEN v1.0")
    if raw.get("ticket")!="M11-006":
        raise ValueError("M11-006 registry ticket mismatch")
    return raw


def make_human_decision(
    *,
    decision_id: str,
    review_item_id: str | None,
    decision_type: str,
    actor_id: str,
    decided_at: str,
    rationale: str,
    registry: Mapping[str,object],
) -> HumanDecision:
    if decision_type not in set(registry["human_decision_types"]):
        raise ValueError("unsupported human decision type")
    if not decision_id.strip() or not actor_id.strip() or not rationale.strip():
        raise ValueError("human decision id, actor, and rationale required")
    _parse_ts(decided_at)
    if decision_type in {"ACKNOWLEDGE_REVIEW","RESOLVE_REVIEW","DEFER_REVIEW"} and not review_item_id:
        raise ValueError("review decision requires review_item_id")
    payload={
        "decision_id":decision_id,"review_item_id":review_item_id,"decision_type":decision_type,
        "actor_id":actor_id,"decided_at":decided_at,"rationale":rationale.strip(),
    }
    return HumanDecision(
        decision_id=decision_id,review_item_id=review_item_id,decision_type=decision_type,
        actor_id=actor_id,decided_at=decided_at,rationale=rationale.strip(),
        decision_fingerprint=_hash(payload),
    )


def _validate_artifacts(
    *,
    opportunity: SellerOpportunityResult,
    strategy: PropertySellerStrategy,
    scenario: ScenarioSensitivityResult | None,
    timeline: SellerDecisionTimeline,
    communication: SellerCommunicationProjection,
) -> str:
    subject=opportunity.subject_property_id
    for obj,label in ((strategy,"strategy"),(timeline,"timeline"),(communication,"communication")):
        if obj.subject_property_id!=subject:
            raise ValueError(f"{label} property mismatch")
    if scenario is not None and scenario.subject_property_id!=subject:
        raise ValueError("scenario property mismatch")
    for obj,label in ((opportunity,"M11-001"),(strategy,"M11-002"),(timeline,"M11-004"),(communication,"M11-005")):
        if obj.public_eligible is not False or obj.external_action_capability!="NONE":
            raise ValueError(f"{label} workspace eligibility boundary violated")
    if scenario is not None and (scenario.public_eligible is not False or scenario.external_action_capability!="NONE"):
        raise ValueError("M11-003 workspace eligibility boundary violated")
    return subject


def _artifact_ref(kind: str, fp: str, status: str) -> ArtifactRef:
    _validate_fp(fp,f"{kind} fingerprint")
    payload={"artifact_type":kind,"artifact_fingerprint":fp,"status":status}
    return ArtifactRef(kind,fp,status,_hash(payload))


def _review_items(
    *,
    timeline: SellerDecisionTimeline,
    decisions: tuple[HumanDecision,...],
    registry: Mapping[str,object],
) -> tuple[ReviewItem,...]:
    decision_by_review={}
    for d in decisions:
        if d.review_item_id:
            decision_by_review.setdefault(d.review_item_id,[]).append(d)

    items=[]
    current_id=timeline.current_snapshot_id
    for entry in timeline.entries:
        event=entry.monitoring_event
        if event is None:
            continue
        item_id=f"REVIEW-{event.event_id}"
        related=sorted(decision_by_review.get(item_id,()),key=lambda x:(_parse_ts(x.decided_at),x.decision_id))
        ack=None
        resolved=None
        status="PENDING"
        for d in related:
            if d.decision_type=="ACKNOWLEDGE_REVIEW":
                ack=d.decision_id
                status="ACKNOWLEDGED"
            elif d.decision_type=="RESOLVE_REVIEW":
                resolved=d.decision_id
                status="RESOLVED"
            elif d.decision_type=="DEFER_REVIEW":
                status="PENDING"
        if entry.snapshot_id!=current_id and status not in {"RESOLVED"}:
            status="SUPERSEDED"
        payload={
            "review_item_id":item_id,
            "source_event_fingerprint":event.event_fingerprint,
            "snapshot_id":entry.snapshot_id,
            "status":status,
            "reasons":event.reasons,
            "acknowledged_by_decision_id":ack,
            "resolved_by_decision_id":resolved,
        }
        items.append(ReviewItem(
            review_item_id=item_id,
            source_event_fingerprint=event.event_fingerprint,
            snapshot_id=entry.snapshot_id,
            status=status,
            reasons=event.reasons,
            acknowledged_by_decision_id=ack,
            resolved_by_decision_id=resolved,
            review_item_fingerprint=_hash(payload),
        ))
    return tuple(sorted(items,key=lambda x:x.review_item_id))


def _validate_decisions(decisions: tuple[HumanDecision,...], registry: Mapping[str,object]) -> None:
    seen=set()
    for d in decisions:
        if d.decision_id in seen:
            raise ValueError("duplicate human decision_id")
        seen.add(d.decision_id)
        if d.decision_type not in set(registry["human_decision_types"]):
            raise ValueError("unsupported human decision type")
        _validate_fp(d.decision_fingerprint,"decision_fingerprint")


def _validate_prohibited(case: SellerIntelligenceCase, registry: Mapping[str,object]) -> None:
    prohibited=set(registry["prohibited_output_fields"])
    d=asdict(case)
    if set(d)&prohibited:
        raise ValueError("prohibited workspace output field present")


def build_seller_intelligence_case(
    *,
    case_id: str,
    opportunity: SellerOpportunityResult,
    strategy: PropertySellerStrategy,
    timeline: SellerDecisionTimeline,
    communication: SellerCommunicationProjection,
    m11_001_certified: bool,
    m11_002_certified: bool,
    m11_004_certified: bool,
    m11_005_certified: bool,
    m11_001_evidence_fingerprint: str,
    m11_002_evidence_fingerprint: str,
    m11_004_evidence_fingerprint: str,
    m11_005_evidence_fingerprint: str,
    registry: Mapping[str,object],
    scenario: ScenarioSensitivityResult | None = None,
    m11_003_certified: bool = False,
    m11_003_evidence_fingerprint: str | None = None,
    human_decisions: Iterable[HumanDecision] = (),
) -> SellerIntelligenceCase:
    if not case_id.strip():
        raise ValueError("case_id required")
    if not (m11_001_certified and m11_002_certified and m11_004_certified and m11_005_certified):
        raise ValueError("certified M11-001, M11-002, M11-004, and M11-005 inputs required")
    fps=[m11_001_evidence_fingerprint,m11_002_evidence_fingerprint,m11_004_evidence_fingerprint,m11_005_evidence_fingerprint]
    if scenario is not None:
        if m11_003_certified is not True or m11_003_evidence_fingerprint is None:
            raise ValueError("certified M11-003 scenario input required")
        fps.append(m11_003_evidence_fingerprint)
    for fp in fps:
        _validate_fp(fp,"evidence fingerprint")

    subject=_validate_artifacts(
        opportunity=opportunity,strategy=strategy,scenario=scenario,timeline=timeline,communication=communication
    )
    decisions=tuple(human_decisions)
    _validate_decisions(decisions,registry)

    current=[
        _artifact_ref("M11-001_OPPORTUNITY",opportunity.result_fingerprint,"CURRENT"),
        _artifact_ref("M11-002_STRATEGY",strategy.strategy_fingerprint,"CURRENT"),
        _artifact_ref("M11-004_TIMELINE",timeline.timeline_fingerprint,"CURRENT"),
        _artifact_ref("M11-005_COMMUNICATION",communication.projection_fingerprint,"CURRENT"),
    ]
    if scenario is not None:
        current.append(_artifact_ref("M11-003_SCENARIO",scenario.scenario_fingerprint,"CURRENT"))

    superseded=[]
    for entry in timeline.entries[:-1]:
        superseded.append(_artifact_ref(
            "M11-002_STRATEGY_SNAPSHOT",entry.strategy_fingerprint,"SUPERSEDED"
        ))

    reviews=_review_items(timeline=timeline,decisions=decisions,registry=registry)
    open_reviews=[r for r in reviews if r.status in {"PENDING","ACKNOWLEDGED"}]
    next_safe=registry["next_safe_steps"]["OPEN_REVIEW" if open_reviews else "NO_OPEN_REVIEW"]

    limitations=tuple(sorted(set(strategy.limitations) | set(communication.limitations)))
    source_fps=set(fps) | {
        opportunity.result_fingerprint,strategy.strategy_fingerprint,timeline.timeline_fingerprint,
        communication.projection_fingerprint,
    }
    if scenario is not None:
        source_fps.add(scenario.scenario_fingerprint)

    payload={
        "case_id":case_id,"subject_property_id":subject,
        "current_artifacts":[x.artifact_ref_fingerprint for x in sorted(current,key=lambda x:x.artifact_type)],
        "superseded_artifacts":[x.artifact_ref_fingerprint for x in sorted(superseded,key=lambda x:x.artifact_fingerprint)],
        "review_items":[x.review_item_fingerprint for x in reviews],
        "human_decisions":[x.decision_fingerprint for x in sorted(decisions,key=lambda x:x.decision_id)],
        "limitations":limitations,"next_safe_step":next_safe,
        "source_fingerprints":sorted(source_fps),
        "output_tier":"INTERNAL","public_eligible":False,"external_action_capability":"NONE",
    }
    case=SellerIntelligenceCase(
        case_id=case_id,
        subject_property_id=subject,
        current_artifacts=tuple(sorted(current,key=lambda x:x.artifact_type)),
        superseded_artifacts=tuple(sorted(superseded,key=lambda x:x.artifact_fingerprint)),
        review_items=reviews,
        human_decisions=tuple(sorted(decisions,key=lambda x:x.decision_id)),
        limitations=limitations,
        next_safe_step=next_safe,
        output_tier="INTERNAL",
        public_eligible=False,
        external_action_capability="NONE",
        case_fingerprint=_hash(payload),
    )
    _validate_prohibited(case,registry)
    return case
