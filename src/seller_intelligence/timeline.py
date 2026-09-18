from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from hashlib import sha256
import json
from pathlib import Path
from typing import Iterable, Mapping
import yaml

from src.seller_intelligence.scenario import ScenarioSensitivityResult
from src.seller_intelligence.strategy import PropertySellerStrategy


def _hash(payload: object) -> str:
    raw=json.dumps(payload,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode("utf-8")
    return sha256(raw).hexdigest()


def _validate_fingerprint(value: str, label: str) -> None:
    if len(value)!=64 or any(c not in "0123456789abcdef" for c in value):
        raise ValueError(f"{label} must be lowercase sha256")


def _parse_timestamp(value: str) -> datetime:
    try:
        dt=datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("snapshot observed_at must be ISO-8601") from exc
    if dt.tzinfo is None:
        raise ValueError("snapshot observed_at must include timezone")
    return dt


@dataclass(frozen=True)
class GovernedTimelineSnapshot:
    snapshot_id: str
    observed_at: str
    strategy: PropertySellerStrategy
    strategy_certified: bool
    strategy_evidence_fingerprint: str
    scenario: ScenarioSensitivityResult | None = None
    scenario_certified: bool = False
    scenario_evidence_fingerprint: str | None = None


@dataclass(frozen=True)
class TimelineChange:
    target: str
    prior_status: str
    current_status: str
    prior_state: str | None
    current_state: str | None
    transition: str
    change_fingerprint: str


@dataclass(frozen=True)
class MonitoringEvent:
    event_id: str
    snapshot_id: str
    observed_at: str
    event_type: str
    human_review_required: bool
    reasons: tuple[str,...]
    instruction: str
    public_eligible: bool
    external_action_capability: str
    event_fingerprint: str


@dataclass(frozen=True)
class TimelineEntry:
    snapshot_id: str
    observed_at: str
    strategy_fingerprint: str
    prior_snapshot_id: str | None
    prior_snapshot_superseded: bool
    changes: tuple[TimelineChange,...]
    monitoring_event: MonitoringEvent | None
    strategy_lineage_fingerprints: tuple[str,...]
    hypothetical_lineage_fingerprints: tuple[str,...]
    entry_fingerprint: str


@dataclass(frozen=True)
class SellerDecisionTimeline:
    subject_property_id: str
    entries: tuple[TimelineEntry,...]
    current_snapshot_id: str
    superseded_snapshot_ids: tuple[str,...]
    output_tier: str
    public_eligible: bool
    external_action_capability: str
    timeline_fingerprint: str


def load_seller_timeline_registry(path: str|Path) -> dict:
    raw=yaml.safe_load(Path(path).read_text())
    if raw.get("seller_timeline_registry_id")!="STH-M11-004-SELLER-DECISION-TIMELINE-v1.0":
        raise ValueError("unexpected M11-004 seller timeline registry id")
    if str(raw.get("version"))!="1.0.0" or raw.get("status")!="FROZEN":
        raise ValueError("M11-004 registry must be FROZEN v1.0")
    if raw.get("ticket")!="M11-004":
        raise ValueError("M11-004 registry ticket mismatch")
    return raw


def _strategy_surface(strategy: PropertySellerStrategy) -> dict[str,tuple[str,str|None]]:
    result={
        "BUYER_ALTERNATIVE_SET":("CURRENT",strategy.buyer_alternative_set_fingerprint),
        "COMPETITIVE_PRESSURE":("CURRENT",strategy.competitive_pressure_level),
    }
    for dimension in strategy.dimensions:
        result[dimension.dimension]=(dimension.status,dimension.state)
    for trigger in strategy.review_triggers:
        result[f"REVIEW_DAY_{trigger.day}"]=(
            "CURRENT",
            "TRIGGERED" if trigger.triggered else "NOT_TRIGGERED",
        )
    return result


def _transition(
    prior_status: str,
    prior_state: str|None,
    current_status: str,
    current_state: str|None,
) -> str:
    if prior_status=="MISSING" and current_status=="MISSING":
        return "REMAINED_MISSING"
    if prior_status=="SUPPRESSED" and current_status=="SUPPRESSED":
        return "REMAINED_SUPPRESSED"
    if current_status=="MISSING" and prior_status!="MISSING":
        return "BECAME_MISSING"
    if current_status=="SUPPRESSED" and prior_status!="SUPPRESSED":
        return "BECAME_SUPPRESSED"
    if current_status=="CURRENT" and prior_status!="CURRENT":
        return "NEWLY_CURRENT"
    if prior_status==current_status and prior_state==current_state:
        return "UNCHANGED"
    return "CHANGED"


def _changes(
    *,
    prior: PropertySellerStrategy,
    current: PropertySellerStrategy,
    registry: Mapping[str,object],
) -> tuple[TimelineChange,...]:
    p=_strategy_surface(prior)
    c=_strategy_surface(current)
    tracked=tuple(str(x) for x in registry["tracked_strategy_targets"])
    if set(p)!=set(tracked) or set(c)!=set(tracked):
        raise ValueError("M11-004 tracked strategy surface mismatch")
    out=[]
    for target in tracked:
        ps,pv=p[target]
        cs,cv=c[target]
        trans=_transition(ps,pv,cs,cv)
        payload={
            "target":target,
            "prior_status":ps,
            "current_status":cs,
            "prior_state":pv,
            "current_state":cv,
            "transition":trans,
        }
        out.append(TimelineChange(
            target=target,
            prior_status=ps,
            current_status=cs,
            prior_state=pv,
            current_state=cv,
            transition=trans,
            change_fingerprint=_hash(payload),
        ))
    return tuple(out)


def _event_reasons(changes: tuple[TimelineChange,...]) -> tuple[str,...]:
    reasons=[]
    for change in changes:
        if change.transition in {"CHANGED","NEWLY_CURRENT","BECAME_MISSING","BECAME_SUPPRESSED"}:
            reasons.append(f"{change.target}:{change.transition}")
    return tuple(sorted(reasons))


def _validate_snapshot(snapshot: GovernedTimelineSnapshot) -> None:
    if not snapshot.snapshot_id.strip():
        raise ValueError("snapshot_id required")
    _parse_timestamp(snapshot.observed_at)
    if snapshot.strategy_certified is not True:
        raise ValueError("certified M11-002 strategy snapshot required")
    _validate_fingerprint(snapshot.strategy_evidence_fingerprint,"strategy_evidence_fingerprint")
    s=snapshot.strategy
    if s.output_tier!="SELLER" or s.public_eligible is not False or s.external_action_capability!="NONE":
        raise ValueError("strategy snapshot eligibility boundary violated")
    if snapshot.scenario is None:
        if snapshot.scenario_certified is True or snapshot.scenario_evidence_fingerprint is not None:
            raise ValueError("scenario certification metadata supplied without scenario")
    else:
        if snapshot.scenario_certified is not True:
            raise ValueError("scenario context must be certified M11-003 output")
        if snapshot.scenario_evidence_fingerprint is None:
            raise ValueError("scenario evidence fingerprint required")
        _validate_fingerprint(snapshot.scenario_evidence_fingerprint,"scenario_evidence_fingerprint")
        sc=snapshot.scenario
        if sc.subject_property_id!=s.subject_property_id:
            raise ValueError("scenario/strategy property mismatch")
        if sc.baseline_strategy_fingerprint!=s.strategy_fingerprint:
            raise ValueError("scenario baseline does not match snapshot strategy")
        if sc.hypothetical_only is not True or sc.public_eligible is not False or sc.external_action_capability!="NONE":
            raise ValueError("scenario snapshot boundary violated")


def _validate_prohibited_fields(timeline: SellerDecisionTimeline, registry: Mapping[str,object]) -> None:
    prohibited=set(str(x) for x in registry["prohibited_output_fields"])
    def walk(value: object) -> None:
        if hasattr(value,"__dataclass_fields__"):
            d=asdict(value)
            overlap=set(d)&prohibited
            if overlap:
                raise ValueError(f"prohibited timeline output fields present: {sorted(overlap)}")
            for item in d.values():
                walk(item)
        elif isinstance(value,dict):
            for item in value.values():
                walk(item)
        elif isinstance(value,(list,tuple)):
            for item in value:
                walk(item)
    walk(timeline)


def build_seller_decision_timeline(
    *,
    snapshots: Iterable[GovernedTimelineSnapshot],
    registry: Mapping[str,object],
) -> SellerDecisionTimeline:
    rows=tuple(snapshots)
    if not rows:
        raise ValueError("at least one certified strategy snapshot required")

    seen=set()
    parsed=[]
    subject=None
    for snapshot in rows:
        _validate_snapshot(snapshot)
        if snapshot.snapshot_id in seen:
            raise ValueError("duplicate snapshot_id")
        seen.add(snapshot.snapshot_id)
        if subject is None:
            subject=snapshot.strategy.subject_property_id
        elif snapshot.strategy.subject_property_id!=subject:
            raise ValueError("timeline snapshots must belong to one property")
        parsed.append((_parse_timestamp(snapshot.observed_at),snapshot))

    parsed.sort(key=lambda x:(x[0],x[1].snapshot_id))
    times=[x[0] for x in parsed]
    if len(times)!=len(set(times)):
        raise ValueError("timeline snapshot timestamps must be unique")

    entries=[]
    prior_snapshot=None
    for _,snapshot in parsed:
        strategy_lineage=tuple(sorted(set(snapshot.strategy.lineage_fingerprints) | {
            snapshot.strategy.strategy_fingerprint,
            snapshot.strategy_evidence_fingerprint,
        }))
        hypothetical=()
        if snapshot.scenario is not None:
            hypothetical=tuple(sorted(set(snapshot.scenario.hypothetical_assumption_fingerprints) | {
                snapshot.scenario.scenario_fingerprint,
                str(snapshot.scenario_evidence_fingerprint),
            }))
            if set(strategy_lineage) & set(hypothetical):
                raise ValueError("strategy fact lineage and hypothetical lineage collision")

        changes=()
        event=None
        prior_id=None
        superseded=False
        if prior_snapshot is not None:
            prior_id=prior_snapshot.snapshot_id
            superseded=True
            changes=_changes(prior=prior_snapshot.strategy,current=snapshot.strategy,registry=registry)
            reasons=_event_reasons(changes)
            if reasons:
                event_payload={
                    "snapshot_id":snapshot.snapshot_id,
                    "observed_at":snapshot.observed_at,
                    "event_type":"HUMAN_REVIEW_REQUIRED",
                    "reasons":reasons,
                    "public_eligible":False,
                    "external_action_capability":"NONE",
                }
                event=MonitoringEvent(
                    event_id=f"{snapshot.snapshot_id}-REVIEW",
                    snapshot_id=snapshot.snapshot_id,
                    observed_at=snapshot.observed_at,
                    event_type="HUMAN_REVIEW_REQUIRED",
                    human_review_required=True,
                    reasons=reasons,
                    instruction=(
                        "Review the certified evidence and strategy changes. "
                        "This monitoring event does not recommend or execute a price change, alter strategy, publish information, or authorize an external action."
                    ),
                    public_eligible=False,
                    external_action_capability="NONE",
                    event_fingerprint=_hash(event_payload),
                )

        entry_payload={
            "snapshot_id":snapshot.snapshot_id,
            "observed_at":snapshot.observed_at,
            "strategy_fingerprint":snapshot.strategy.strategy_fingerprint,
            "prior_snapshot_id":prior_id,
            "prior_snapshot_superseded":superseded,
            "changes":[x.change_fingerprint for x in changes],
            "monitoring_event":event.event_fingerprint if event else None,
            "strategy_lineage_fingerprints":strategy_lineage,
            "hypothetical_lineage_fingerprints":hypothetical,
        }
        entries.append(TimelineEntry(
            snapshot_id=snapshot.snapshot_id,
            observed_at=snapshot.observed_at,
            strategy_fingerprint=snapshot.strategy.strategy_fingerprint,
            prior_snapshot_id=prior_id,
            prior_snapshot_superseded=superseded,
            changes=changes,
            monitoring_event=event,
            strategy_lineage_fingerprints=strategy_lineage,
            hypothetical_lineage_fingerprints=hypothetical,
            entry_fingerprint=_hash(entry_payload),
        ))
        prior_snapshot=snapshot

    current=entries[-1].snapshot_id
    superseded_ids=tuple(x.snapshot_id for x in entries[:-1])
    payload={
        "subject_property_id":subject,
        "entries":[x.entry_fingerprint for x in entries],
        "current_snapshot_id":current,
        "superseded_snapshot_ids":superseded_ids,
        "output_tier":"SELLER",
        "public_eligible":False,
        "external_action_capability":"NONE",
    }
    timeline=SellerDecisionTimeline(
        subject_property_id=str(subject),
        entries=tuple(entries),
        current_snapshot_id=current,
        superseded_snapshot_ids=superseded_ids,
        output_tier="SELLER",
        public_eligible=False,
        external_action_capability="NONE",
        timeline_fingerprint=_hash(payload),
    )
    _validate_prohibited_fields(timeline,registry)
    return timeline
