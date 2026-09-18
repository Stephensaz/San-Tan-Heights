from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from hashlib import sha256
import json
from pathlib import Path
from typing import Iterable, Mapping
import yaml

from src.seller_intelligence.workspace import SellerIntelligenceCase
from src.seller_intelligence.timeline import SellerDecisionTimeline


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
        raise ValueError("outcome observed_at must be ISO-8601") from exc
    if dt.tzinfo is None:
        raise ValueError("outcome observed_at must include timezone")
    return dt


@dataclass(frozen=True)
class ObservedOutcome:
    outcome_id: str
    subject_property_id: str
    outcome_type: str
    outcome_state: str
    observed_at: str
    source_fingerprint: str
    notes: str
    outcome_fingerprint: str


@dataclass(frozen=True)
class AssociationRecord:
    association_id: str
    outcome_id: str
    association_type: str
    source_fingerprints: tuple[str,...]
    statement: str
    causal_claim: bool
    association_fingerprint: str


@dataclass(frozen=True)
class CalibrationCandidate:
    candidate_id: str
    candidate_type: str
    outcome_id: str
    rationale: str
    advisory_only: bool
    promotion_status: str
    source_fingerprints: tuple[str,...]
    candidate_fingerprint: str


@dataclass(frozen=True)
class EffectivenessLearningResult:
    case_id: str
    subject_property_id: str
    observed_outcomes: tuple[ObservedOutcome,...]
    associations: tuple[AssociationRecord,...]
    calibration_candidates: tuple[CalibrationCandidate,...]
    unknown_outcome_ids: tuple[str,...]
    source_case_fingerprint: str
    output_tier: str
    public_eligible: bool
    external_action_capability: str
    learning_fingerprint: str


def load_effectiveness_registry(path: str|Path) -> dict:
    raw=yaml.safe_load(Path(path).read_text())
    if raw.get("seller_effectiveness_registry_id")!="STH-M11-007-EFFECTIVENESS-LEARNING-v1.0":
        raise ValueError("unexpected M11-007 effectiveness registry id")
    if str(raw.get("version"))!="1.0.0" or raw.get("status")!="FROZEN":
        raise ValueError("M11-007 registry must be FROZEN v1.0")
    if raw.get("ticket")!="M11-007":
        raise ValueError("M11-007 registry ticket mismatch")
    return raw


def make_observed_outcome(
    *,
    outcome_id: str,
    subject_property_id: str,
    outcome_type: str,
    outcome_state: str,
    observed_at: str,
    source_fingerprint: str,
    notes: str,
    registry: Mapping[str,object],
) -> ObservedOutcome:
    if not outcome_id.strip() or not subject_property_id.strip():
        raise ValueError("outcome id and subject property id required")
    if outcome_type not in registry["outcome_types"]:
        raise ValueError("unsupported observed outcome type")
    allowed=set(registry["outcome_types"][outcome_type]["allowed_states"])
    if outcome_state not in allowed:
        raise ValueError("unsupported observed outcome state")
    _parse_ts(observed_at)
    _validate_fp(source_fingerprint,"outcome source fingerprint")
    payload={
        "outcome_id":outcome_id,
        "subject_property_id":subject_property_id,
        "outcome_type":outcome_type,
        "outcome_state":outcome_state,
        "observed_at":observed_at,
        "source_fingerprint":source_fingerprint,
        "notes":notes.strip(),
    }
    return ObservedOutcome(
        outcome_id=outcome_id,
        subject_property_id=subject_property_id,
        outcome_type=outcome_type,
        outcome_state=outcome_state,
        observed_at=observed_at,
        source_fingerprint=source_fingerprint,
        notes=notes.strip(),
        outcome_fingerprint=_hash(payload),
    )


def _validate_case(case: SellerIntelligenceCase) -> None:
    if case.output_tier!="INTERNAL" or case.public_eligible is not False:
        raise ValueError("M11-006 case eligibility boundary violated")
    if case.external_action_capability!="NONE":
        raise ValueError("M11-006 case external action boundary violated")


def _association_records(
    *,
    case: SellerIntelligenceCase,
    timeline: SellerDecisionTimeline,
    outcome: ObservedOutcome,
) -> tuple[AssociationRecord,...]:
    observed=_parse_ts(outcome.observed_at)
    case_event_fps={item.source_event_fingerprint for item in case.review_items}
    prior_reviews=[]
    for entry in timeline.entries:
        event=entry.monitoring_event
        if event is None:
            continue
        if event.event_fingerprint not in case_event_fps:
            continue
        event_time=_parse_ts(event.observed_at)
        if event_time<=observed:
            prior_reviews.append(event.event_fingerprint)

    prior_decisions=[]
    for decision in case.human_decisions:
        try:
            decided=datetime.fromisoformat(decision.decided_at)
        except ValueError:
            continue
        if decided.tzinfo is not None and decided<=observed:
            prior_decisions.append(decision.decision_fingerprint)

    records=[]
    if prior_reviews:
        fps=tuple(sorted(set(prior_reviews)))
        payload={
            "outcome_id":outcome.outcome_id,
            "association_type":"PRECEDED_BY_REVIEW_EVENT",
            "source_fingerprints":fps,
        }
        records.append(AssociationRecord(
            association_id=f"{outcome.outcome_id}-REVIEW",
            outcome_id=outcome.outcome_id,
            association_type="PRECEDED_BY_REVIEW_EVENT",
            source_fingerprints=fps,
            statement="A governed human-review event existed in the certified case before this observed outcome was evaluated. This is an association, not evidence of causation.",
            causal_claim=False,
            association_fingerprint=_hash(payload),
        ))
    else:
        payload={"outcome_id":outcome.outcome_id,"association_type":"NO_PRIOR_REVIEW_EVENT","source_fingerprints":()}
        records.append(AssociationRecord(
            association_id=f"{outcome.outcome_id}-NO-REVIEW",
            outcome_id=outcome.outcome_id,
            association_type="NO_PRIOR_REVIEW_EVENT",
            source_fingerprints=(),
            statement="No governed review event is linked in the certified case for this observed outcome.",
            causal_claim=False,
            association_fingerprint=_hash(payload),
        ))

    if prior_decisions:
        fps=tuple(sorted(set(prior_decisions)))
        payload={
            "outcome_id":outcome.outcome_id,
            "association_type":"PRECEDED_BY_HUMAN_DECISION",
            "source_fingerprints":fps,
        }
        records.append(AssociationRecord(
            association_id=f"{outcome.outcome_id}-DECISION",
            outcome_id=outcome.outcome_id,
            association_type="PRECEDED_BY_HUMAN_DECISION",
            source_fingerprints=fps,
            statement="One or more recorded human decisions preceded this observed outcome. This is an association, not evidence that the decision caused the outcome.",
            causal_claim=False,
            association_fingerprint=_hash(payload),
        ))
    else:
        payload={"outcome_id":outcome.outcome_id,"association_type":"NO_PRIOR_HUMAN_DECISION","source_fingerprints":()}
        records.append(AssociationRecord(
            association_id=f"{outcome.outcome_id}-NO-DECISION",
            outcome_id=outcome.outcome_id,
            association_type="NO_PRIOR_HUMAN_DECISION",
            source_fingerprints=(),
            statement="No recorded human decision preceded this observed outcome.",
            causal_claim=False,
            association_fingerprint=_hash(payload),
        ))
    return tuple(records)


def _calibration_candidates(
    *,
    outcome: ObservedOutcome,
    associations: tuple[AssociationRecord,...],
    registry: Mapping[str,object],
) -> tuple[CalibrationCandidate,...]:
    candidates=[]
    assoc_types={a.association_type for a in associations}
    for rule_id,rule in registry["calibration_candidate_rules"].items():
        if outcome.outcome_type!=rule["outcome_type"]:
            continue
        if outcome.outcome_state not in set(rule["allowed_outcome_states"]):
            continue
        if rule.get("require_prior_review_event") and "PRECEDED_BY_REVIEW_EVENT" not in assoc_types:
            continue
        source={outcome.outcome_fingerprint}
        for a in associations:
            source.add(a.association_fingerprint)
            source.update(a.source_fingerprints)
        source_tuple=tuple(sorted(source))
        rationale=(
            f"Observed outcome {outcome.outcome_id} ({outcome.outcome_type}={outcome.outcome_state}) "
            f"matches advisory calibration rule {rule_id}. Review in M11-008; do not treat this as causal proof or an automatic policy change."
        )
        payload={
            "candidate_id":f"CAL-{outcome.outcome_id}-{rule_id}",
            "candidate_type":rule["candidate_type"],
            "outcome_id":outcome.outcome_id,
            "rationale":rationale,
            "advisory_only":True,
            "promotion_status":"NOT_PROMOTED",
            "source_fingerprints":source_tuple,
        }
        candidates.append(CalibrationCandidate(
            candidate_id=payload["candidate_id"],
            candidate_type=payload["candidate_type"],
            outcome_id=outcome.outcome_id,
            rationale=rationale,
            advisory_only=True,
            promotion_status="NOT_PROMOTED",
            source_fingerprints=source_tuple,
            candidate_fingerprint=_hash(payload),
        ))
    return tuple(candidates)


def _validate_prohibited(result: EffectivenessLearningResult, registry: Mapping[str,object]) -> None:
    prohibited=set(registry["prohibited_output_fields"])
    def walk(v: object) -> None:
        if hasattr(v,"__dataclass_fields__"):
            d=asdict(v)
            if set(d)&prohibited:
                raise ValueError("prohibited effectiveness output field present")
            for item in d.values():
                walk(item)
        elif isinstance(v,dict):
            for item in v.values():
                walk(item)
        elif isinstance(v,(tuple,list)):
            for item in v:
                walk(item)
    walk(result)


def evaluate_effectiveness(
    *,
    case: SellerIntelligenceCase,
    timeline: SellerDecisionTimeline,
    m11_004_certified: bool,
    m11_004_evidence_fingerprint: str,
    m11_006_certified: bool,
    m11_006_evidence_fingerprint: str,
    outcomes: Iterable[ObservedOutcome],
    registry: Mapping[str,object],
) -> EffectivenessLearningResult:
    if m11_006_certified is not True:
        raise ValueError("certified M11-006 case required")
    if m11_004_certified is not True:
        raise ValueError("certified M11-004 timeline required")
    _validate_fp(m11_006_evidence_fingerprint,"m11_006_evidence_fingerprint")
    _validate_fp(m11_004_evidence_fingerprint,"m11_004_evidence_fingerprint")
    _validate_case(case)
    if timeline.subject_property_id!=case.subject_property_id:
        raise ValueError("timeline/case property mismatch")
    if timeline.public_eligible is not False or timeline.external_action_capability!="NONE":
        raise ValueError("M11-004 timeline effectiveness boundary violated")
    timeline_refs={
        x.artifact_fingerprint
        for x in case.current_artifacts
        if x.artifact_type=="M11-004_TIMELINE"
    }
    if timeline.timeline_fingerprint not in timeline_refs:
        raise ValueError("case does not reference supplied certified timeline")

    rows=tuple(outcomes)
    seen=set()
    ordered=[]
    for outcome in rows:
        if outcome.outcome_id in seen:
            raise ValueError("duplicate observed outcome_id")
        seen.add(outcome.outcome_id)
        if outcome.subject_property_id!=case.subject_property_id:
            raise ValueError("observed outcome property mismatch")
        _validate_fp(outcome.source_fingerprint,"outcome source fingerprint")
        _validate_fp(outcome.outcome_fingerprint,"outcome fingerprint")
        ordered.append((_parse_ts(outcome.observed_at),outcome))
    ordered.sort(key=lambda x:(x[0],x[1].outcome_id))

    associations=[]
    candidates=[]
    for _,outcome in ordered:
        records=_association_records(case=case,timeline=timeline,outcome=outcome)
        associations.extend(records)
        candidates.extend(_calibration_candidates(outcome=outcome,associations=records,registry=registry))

    ordered_outcomes=tuple(x[1] for x in ordered)
    associations_tuple=tuple(sorted(associations,key=lambda x:x.association_id))
    candidates_tuple=tuple(sorted(candidates,key=lambda x:x.candidate_id))
    unknown=tuple(sorted(o.outcome_id for o in ordered_outcomes if o.outcome_state=="UNKNOWN"))
    source_fps={
        case.case_fingerprint,
        timeline.timeline_fingerprint,
        m11_004_evidence_fingerprint,
        m11_006_evidence_fingerprint,
        *(o.outcome_fingerprint for o in ordered_outcomes),
        *(a.association_fingerprint for a in associations_tuple),
    }
    payload={
        "case_id":case.case_id,
        "subject_property_id":case.subject_property_id,
        "observed_outcomes":[x.outcome_fingerprint for x in ordered_outcomes],
        "associations":[x.association_fingerprint for x in associations_tuple],
        "calibration_candidates":[x.candidate_fingerprint for x in candidates_tuple],
        "unknown_outcome_ids":unknown,
        "source_case_fingerprint":case.case_fingerprint,
        "source_fingerprints":sorted(source_fps),
        "output_tier":"INTERNAL",
        "public_eligible":False,
        "external_action_capability":"NONE",
    }
    result=EffectivenessLearningResult(
        case_id=case.case_id,
        subject_property_id=case.subject_property_id,
        observed_outcomes=ordered_outcomes,
        associations=associations_tuple,
        calibration_candidates=candidates_tuple,
        unknown_outcome_ids=unknown,
        source_case_fingerprint=case.case_fingerprint,
        output_tier="INTERNAL",
        public_eligible=False,
        external_action_capability="NONE",
        learning_fingerprint=_hash(payload),
    )
    _validate_prohibited(result,registry)
    return result
