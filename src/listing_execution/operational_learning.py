from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
import json
from pathlib import Path
from typing import Iterable, Mapping
import yaml

from src.listing_execution.authorized_execution import ExecutionReceipt
from src.listing_execution.verification_reconciliation import (
    ReconciliationCase,
    RollbackReceipt,
    VerificationReceipt,
)


def _hash(payload: object) -> str:
    raw=json.dumps(payload,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode("utf-8")
    return sha256(raw).hexdigest()


def _validate_fp(value: str, label: str) -> None:
    if len(value)!=64 or any(c not in "0123456789abcdef" for c in value):
        raise ValueError(f"{label} must be lowercase sha256")


def _parse_ts(value: str, label: str) -> datetime:
    try:
        dt=datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{label} must be ISO-8601") from exc
    if dt.tzinfo is None:
        raise ValueError(f"{label} must include timezone")
    return dt


@dataclass(frozen=True)
class OperationalEpisode:
    episode_id: str
    subject_property_id: str
    listing_id: str
    action_type: str
    proposal_fingerprint: str
    approval_fingerprint: str
    authority_fingerprint: str
    execution_receipt: ExecutionReceipt
    verification: VerificationReceipt
    reconciliation_case: ReconciliationCase | None
    rollback_receipt: RollbackReceipt | None
    episode_fingerprint: str


@dataclass(frozen=True)
class OperationalOutcome:
    outcome_id: str
    episode_fingerprint: str
    outcome_type: str
    outcome_state: str
    observed_at: str
    source_fingerprint: str
    notes_fingerprint: str
    immutable: bool
    outcome_fingerprint: str


@dataclass(frozen=True)
class OperationalAssociation:
    association_id: str
    outcome_id: str
    association_type: str
    source_fingerprints: tuple[str,...]
    statement: str
    causal_claim: bool
    association_fingerprint: str


@dataclass(frozen=True)
class OperationalMetrics:
    execution_attempt_count: int
    execution_success_count: int
    duplicate_suppression_count: int
    execution_outcome_unknown_count: int
    verification_count: int
    verification_mismatch_count: int
    verification_outcome_unknown_count: int
    reconciliation_case_count: int
    open_reconciliation_count: int
    rollback_attempt_count: int
    rollback_success_count: int
    rollback_outcome_unknown_count: int
    metrics_fingerprint: str


@dataclass(frozen=True)
class OperationalImprovementCandidate:
    candidate_id: str
    candidate_type: str
    trigger_code: str
    source_fingerprints: tuple[str,...]
    rationale: str
    advisory_only: bool
    promotion_status: str
    candidate_fingerprint: str


@dataclass(frozen=True)
class OperationalLearningResult:
    episodes: tuple[OperationalEpisode,...]
    outcomes: tuple[OperationalOutcome,...]
    associations: tuple[OperationalAssociation,...]
    metrics: OperationalMetrics
    improvement_candidates: tuple[OperationalImprovementCandidate,...]
    unknown_outcome_ids: tuple[str,...]
    public_eligible: bool
    external_action_capability: str
    learning_fingerprint: str


def load_operational_learning_registry(path: str|Path) -> dict:
    raw=yaml.safe_load(Path(path).read_text())
    if raw.get("operational_learning_registry_id")!="STH-M12-004-OPERATIONAL-LEARNING-v1.0":
        raise ValueError("unexpected M12-004 operational learning registry id")
    if str(raw.get("version"))!="1.0.0" or raw.get("status")!="FROZEN":
        raise ValueError("M12-004 registry must be FROZEN v1.0")
    if raw.get("ticket")!="M12-004" or raw.get("parent_ticket")!="M12-003":
        raise ValueError("M12-004 registry lineage mismatch")
    return raw


def make_operational_episode(
    *,
    episode_id: str,
    subject_property_id: str,
    listing_id: str,
    action_type: str,
    proposal_fingerprint: str,
    approval_fingerprint: str,
    authority_fingerprint: str,
    execution_receipt: ExecutionReceipt,
    verification: VerificationReceipt,
    reconciliation_case: ReconciliationCase | None = None,
    rollback_receipt: RollbackReceipt | None = None,
) -> OperationalEpisode:
    if not episode_id.strip() or not subject_property_id.strip() or not listing_id.strip() or not action_type.strip():
        raise ValueError("episode identity and action scope required")
    for value,label in (
        (proposal_fingerprint,"proposal_fingerprint"),
        (approval_fingerprint,"approval_fingerprint"),
        (authority_fingerprint,"authority_fingerprint"),
        (execution_receipt.receipt_fingerprint,"execution receipt fingerprint"),
        (verification.verification_fingerprint,"verification fingerprint"),
    ):
        _validate_fp(value,label)
    if execution_receipt.proposal_fingerprint!=proposal_fingerprint:
        raise ValueError("episode proposal lineage mismatch")
    if execution_receipt.approval_fingerprint!=approval_fingerprint:
        raise ValueError("episode approval lineage mismatch")
    if execution_receipt.authority_fingerprint!=authority_fingerprint:
        raise ValueError("episode authority lineage mismatch")
    if verification.execution_receipt_fingerprint!=execution_receipt.receipt_fingerprint:
        raise ValueError("episode verification lineage mismatch")
    if reconciliation_case is not None:
        if reconciliation_case.execution_receipt_fingerprint!=execution_receipt.receipt_fingerprint:
            raise ValueError("episode reconciliation receipt lineage mismatch")
        if reconciliation_case.verification_fingerprint!=verification.verification_fingerprint:
            raise ValueError("episode reconciliation verification lineage mismatch")
    if rollback_receipt is not None:
        if reconciliation_case is None:
            raise ValueError("rollback receipt requires reconciliation case")
        if rollback_receipt.reconciliation_case_fingerprint!=reconciliation_case.case_fingerprint:
            raise ValueError("episode rollback reconciliation lineage mismatch")
        if rollback_receipt.original_execution_receipt_fingerprint!=execution_receipt.receipt_fingerprint:
            raise ValueError("episode rollback execution lineage mismatch")
        if rollback_receipt.verification_fingerprint!=verification.verification_fingerprint:
            raise ValueError("episode rollback verification lineage mismatch")
    payload={
        "episode_id":episode_id,
        "subject_property_id":subject_property_id,
        "listing_id":listing_id,
        "action_type":action_type,
        "proposal_fingerprint":proposal_fingerprint,
        "approval_fingerprint":approval_fingerprint,
        "authority_fingerprint":authority_fingerprint,
        "execution_receipt_fingerprint":execution_receipt.receipt_fingerprint,
        "verification_fingerprint":verification.verification_fingerprint,
        "reconciliation_case_fingerprint":reconciliation_case.case_fingerprint if reconciliation_case else None,
        "rollback_receipt_fingerprint":rollback_receipt.receipt_fingerprint if rollback_receipt else None,
    }
    return OperationalEpisode(
        episode_id=episode_id,
        subject_property_id=subject_property_id,
        listing_id=listing_id,
        action_type=action_type,
        proposal_fingerprint=proposal_fingerprint,
        approval_fingerprint=approval_fingerprint,
        authority_fingerprint=authority_fingerprint,
        execution_receipt=execution_receipt,
        verification=verification,
        reconciliation_case=reconciliation_case,
        rollback_receipt=rollback_receipt,
        episode_fingerprint=_hash(payload),
    )


def make_operational_outcome(
    *,
    outcome_id: str,
    episode_fingerprint: str,
    outcome_type: str,
    outcome_state: str,
    observed_at: str,
    source_fingerprint: str,
    notes_fingerprint: str,
    registry: Mapping[str,object],
) -> OperationalOutcome:
    if not outcome_id.strip():
        raise ValueError("outcome_id required")
    _validate_fp(episode_fingerprint,"episode_fingerprint")
    _validate_fp(source_fingerprint,"outcome source_fingerprint")
    _validate_fp(notes_fingerprint,"outcome notes_fingerprint")
    _parse_ts(observed_at,"outcome observed_at")
    if outcome_type not in set(registry["outcome_types"]):
        raise ValueError("unsupported operational outcome type")
    if outcome_state not in set(registry["allowed_outcome_states"]):
        raise ValueError("unsupported operational outcome state")
    payload={
        "outcome_id":outcome_id,
        "episode_fingerprint":episode_fingerprint,
        "outcome_type":outcome_type,
        "outcome_state":outcome_state,
        "observed_at":observed_at,
        "source_fingerprint":source_fingerprint,
        "notes_fingerprint":notes_fingerprint,
        "immutable":True,
    }
    return OperationalOutcome(**payload,outcome_fingerprint=_hash(payload))


def _association(outcome: OperationalOutcome, episode: OperationalEpisode, association_type: str, sources: Iterable[str], statement: str) -> OperationalAssociation:
    fps=tuple(sorted(set(sources)))
    payload={
        "association_id":f"{outcome.outcome_id}-{association_type}",
        "outcome_id":outcome.outcome_id,
        "association_type":association_type,
        "source_fingerprints":fps,
        "statement":statement,
        "causal_claim":False,
    }
    return OperationalAssociation(
        association_id=payload["association_id"],
        outcome_id=outcome.outcome_id,
        association_type=association_type,
        source_fingerprints=fps,
        statement=statement,
        causal_claim=False,
        association_fingerprint=_hash(payload),
    )


def _metrics(episodes: tuple[OperationalEpisode,...]) -> OperationalMetrics:
    values={
        "execution_attempt_count":sum(1 for e in episodes if e.execution_receipt.side_effect_attempted),
        "execution_success_count":sum(1 for e in episodes if e.execution_receipt.outcome=="SUCCEEDED"),
        "duplicate_suppression_count":sum(1 for e in episodes if e.execution_receipt.duplicate_suppressed),
        "execution_outcome_unknown_count":sum(1 for e in episodes if e.execution_receipt.outcome_unknown),
        "verification_count":len(episodes),
        "verification_mismatch_count":sum(1 for e in episodes if e.verification.verification_state=="MISMATCH"),
        "verification_outcome_unknown_count":sum(1 for e in episodes if e.verification.verification_state=="OUTCOME_UNKNOWN"),
        "reconciliation_case_count":sum(1 for e in episodes if e.reconciliation_case is not None),
        "open_reconciliation_count":sum(1 for e in episodes if e.reconciliation_case is not None and e.reconciliation_case.state=="OPEN"),
        "rollback_attempt_count":sum(1 for e in episodes if e.rollback_receipt is not None and e.rollback_receipt.side_effect_attempted),
        "rollback_success_count":sum(1 for e in episodes if e.rollback_receipt is not None and e.rollback_receipt.outcome=="SUCCEEDED"),
        "rollback_outcome_unknown_count":sum(1 for e in episodes if e.rollback_receipt is not None and e.rollback_receipt.outcome_unknown),
    }
    return OperationalMetrics(**values,metrics_fingerprint=_hash(values))


def _candidates(episodes: tuple[OperationalEpisode,...], metrics: OperationalMetrics, registry: Mapping[str,object]) -> tuple[OperationalImprovementCandidate,...]:
    triggers=[]
    if metrics.execution_outcome_unknown_count:
        triggers.append("EXECUTION_OUTCOME_UNKNOWN")
    if metrics.verification_mismatch_count:
        triggers.append("VERIFICATION_MISMATCH")
    if metrics.verification_outcome_unknown_count:
        triggers.append("VERIFICATION_OUTCOME_UNKNOWN")
    if metrics.open_reconciliation_count:
        triggers.append("OPEN_RECONCILIATION")
    if metrics.rollback_outcome_unknown_count:
        triggers.append("ROLLBACK_OUTCOME_UNKNOWN")
    out=[]
    for trigger in sorted(set(triggers)):
        rule=registry["improvement_rules"][trigger]
        sources={metrics.metrics_fingerprint}
        for e in episodes:
            if trigger=="EXECUTION_OUTCOME_UNKNOWN" and e.execution_receipt.outcome_unknown:
                sources.add(e.execution_receipt.receipt_fingerprint)
            if trigger=="VERIFICATION_MISMATCH" and e.verification.verification_state=="MISMATCH":
                sources.add(e.verification.verification_fingerprint)
            if trigger=="VERIFICATION_OUTCOME_UNKNOWN" and e.verification.verification_state=="OUTCOME_UNKNOWN":
                sources.add(e.verification.verification_fingerprint)
            if trigger=="OPEN_RECONCILIATION" and e.reconciliation_case is not None and e.reconciliation_case.state=="OPEN":
                sources.add(e.reconciliation_case.case_fingerprint)
            if trigger=="ROLLBACK_OUTCOME_UNKNOWN" and e.rollback_receipt is not None and e.rollback_receipt.outcome_unknown:
                sources.add(e.rollback_receipt.receipt_fingerprint)
        fps=tuple(sorted(sources))
        rationale=f"Observed operational pattern {trigger} warrants controlled M12-005 review. This is advisory and does not establish causation or change live execution policy."
        payload={
            "candidate_id":f"M12-004-{trigger}",
            "candidate_type":rule["candidate_type"],
            "trigger_code":trigger,
            "source_fingerprints":fps,
            "rationale":rationale,
            "advisory_only":True,
            "promotion_status":"NOT_PROMOTED",
        }
        out.append(OperationalImprovementCandidate(**payload,candidate_fingerprint=_hash(payload)))
    return tuple(out)


def evaluate_operational_learning(
    *,
    episodes: Iterable[OperationalEpisode],
    outcomes: Iterable[OperationalOutcome],
    registry: Mapping[str,object],
) -> OperationalLearningResult:
    eps=tuple(sorted(tuple(episodes),key=lambda x:x.episode_id))
    outs=tuple(sorted(tuple(outcomes),key=lambda x:(x.observed_at,x.outcome_id)))
    if not eps:
        raise ValueError("at least one operational episode required")
    seen_eps=set()
    by_fp={}
    for e in eps:
        if e.episode_id in seen_eps:
            raise ValueError("duplicate operational episode_id")
        seen_eps.add(e.episode_id)
        by_fp[e.episode_fingerprint]=e
    seen_out=set()
    associations=[]
    unknown=[]
    for o in outs:
        if o.outcome_id in seen_out:
            raise ValueError("duplicate operational outcome_id")
        seen_out.add(o.outcome_id)
        episode=by_fp.get(o.episode_fingerprint)
        if episode is None:
            raise ValueError("operational outcome episode lineage mismatch")
        if o.outcome_state in {"OUTCOME_UNKNOWN","UNRESOLVED","BLOCKED_OUTCOME_UNKNOWN"}:
            unknown.append(o.outcome_id)
        associations.extend([
            _association(o,episode,"LINKED_EXECUTION",
                (episode.proposal_fingerprint,episode.approval_fingerprint,episode.authority_fingerprint,episode.execution_receipt.receipt_fingerprint),
                "This observed operational outcome is linked to the governed execution chain. The linkage is associative and does not establish causation."),
            _association(o,episode,"LINKED_VERIFICATION",
                (episode.verification.verification_fingerprint,),
                "This observed operational outcome is linked to independent verification evidence. The linkage is associative and does not establish causation."),
        ])
        if episode.reconciliation_case is not None:
            associations.append(_association(o,episode,"LINKED_RECONCILIATION",
                (episode.reconciliation_case.case_fingerprint,),
                "This observed operational outcome is linked to a governed reconciliation case. The linkage is associative and does not establish causation."))
        if episode.rollback_receipt is not None:
            associations.append(_association(o,episode,"LINKED_ROLLBACK",
                (episode.rollback_receipt.receipt_fingerprint,),
                "This observed operational outcome is linked to a governed rollback receipt. The linkage is associative and does not establish causation."))
    associations_tuple=tuple(sorted(associations,key=lambda x:x.association_id))
    metrics=_metrics(eps)
    candidates=_candidates(eps,metrics,registry)
    payload={
        "episodes":[e.episode_fingerprint for e in eps],
        "outcomes":[o.outcome_fingerprint for o in outs],
        "associations":[a.association_fingerprint for a in associations_tuple],
        "metrics_fingerprint":metrics.metrics_fingerprint,
        "candidates":[c.candidate_fingerprint for c in candidates],
        "unknown_outcome_ids":tuple(sorted(unknown)),
        "public_eligible":False,
        "external_action_capability":"NONE",
    }
    return OperationalLearningResult(
        episodes=eps,
        outcomes=outs,
        associations=associations_tuple,
        metrics=metrics,
        improvement_candidates=candidates,
        unknown_outcome_ids=tuple(sorted(unknown)),
        public_eligible=False,
        external_action_capability="NONE",
        learning_fingerprint=_hash(payload),
    )
