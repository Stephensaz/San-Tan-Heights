from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from hashlib import sha256
import json
from pathlib import Path
from typing import Mapping
import yaml

from src.seller_intelligence.workspace import SellerIntelligenceCase


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
class ListingContext:
    listing_id: str
    subject_property_id: str
    listing_status: str
    freshness_state: str
    observed_at: str
    source_fingerprint: str
    context_fingerprint: str


@dataclass(frozen=True)
class AgentJudgment:
    judgment_id: str
    subject_property_id: str
    actor_id: str
    judgment_code: str
    recorded_at: str
    notes_fingerprint: str
    judgment_fingerprint: str


@dataclass(frozen=True)
class ActionIntent:
    intent_id: str
    subject_property_id: str
    action_type: str
    origin: str
    target_review_item_id: str | None
    requested_at: str
    requested_policy_version: str
    intent_fingerprint: str


@dataclass(frozen=True)
class GovernedActionProposal:
    proposal_id: str
    subject_property_id: str
    listing_id: str
    action_type: str
    origin: str
    target_review_item_id: str | None
    reason_codes: tuple[str,...]
    prerequisites: tuple[str,...]
    limitations: tuple[str,...]
    source_case_fingerprint: str
    listing_context_fingerprint: str
    intent_fingerprint: str
    agent_judgment_fingerprint: str | None
    m11_release_evidence_fingerprint: str
    m11_release_certification_root: str
    policy_version: str
    policy_fingerprint: str
    lineage_fingerprints: tuple[str,...]
    proposal_status: str
    approval_state: str
    authorization_state: str
    schedule_state: str
    queue_state: str
    execution_state: str
    publication_state: str
    transmission_state: str
    requires_human_approval: bool
    public_eligible: bool
    external_action_capability: str
    proposal_fingerprint: str


def load_action_proposal_registry(path: str|Path) -> dict:
    raw=yaml.safe_load(Path(path).read_text())
    if raw.get("action_proposal_registry_id")!="STH-M12-001-ACTION-PROPOSAL-v1.0":
        raise ValueError("unexpected M12-001 action proposal registry id")
    if str(raw.get("version"))!="1.0.0" or raw.get("status")!="FROZEN":
        raise ValueError("M12-001 registry must be FROZEN v1.0")
    if raw.get("ticket")!="M12-001" or raw.get("contract_id")!="STH-LISTING-EXECUTION":
        raise ValueError("M12-001 registry lineage mismatch")
    return raw


def policy_fingerprint(registry: Mapping[str,object]) -> str:
    payload={
        "policy":registry["policy"],
        "proposal_state":registry["proposal_state"],
        "required_prerequisites":registry["required_prerequisites"],
        "governance":registry["governance"],
        "prohibited_output_fields":registry["prohibited_output_fields"],
    }
    return _hash(payload)


def make_listing_context(
    *,
    listing_id: str,
    subject_property_id: str,
    listing_status: str,
    freshness_state: str,
    observed_at: str,
    source_fingerprint: str,
    registry: Mapping[str,object],
) -> ListingContext:
    if not listing_id.strip() or not subject_property_id.strip():
        raise ValueError("listing_id and subject_property_id required")
    if listing_status not in set(registry["policy"]["allowed_listing_statuses"]):
        raise ValueError("unsupported listing status")
    if freshness_state!=registry["policy"]["current_freshness_state"]:
        raise ValueError("listing context must be CURRENT")
    _parse_ts(observed_at,"listing context observed_at")
    _validate_fp(source_fingerprint,"listing context source_fingerprint")
    payload={
        "listing_id":listing_id,
        "subject_property_id":subject_property_id,
        "listing_status":listing_status,
        "freshness_state":freshness_state,
        "observed_at":observed_at,
        "source_fingerprint":source_fingerprint,
    }
    return ListingContext(
        listing_id=listing_id,
        subject_property_id=subject_property_id,
        listing_status=listing_status,
        freshness_state=freshness_state,
        observed_at=observed_at,
        source_fingerprint=source_fingerprint,
        context_fingerprint=_hash(payload),
    )


def make_agent_judgment(
    *,
    judgment_id: str,
    subject_property_id: str,
    actor_id: str,
    judgment_code: str,
    recorded_at: str,
    notes_fingerprint: str,
    registry: Mapping[str,object],
) -> AgentJudgment:
    if not judgment_id.strip() or not subject_property_id.strip() or not actor_id.strip():
        raise ValueError("judgment id, property id, and actor id required")
    if judgment_code not in set(registry["policy"]["allowed_judgment_codes"]):
        raise ValueError("unsupported agent judgment code")
    _parse_ts(recorded_at,"agent judgment recorded_at")
    _validate_fp(notes_fingerprint,"agent judgment notes_fingerprint")
    payload={
        "judgment_id":judgment_id,
        "subject_property_id":subject_property_id,
        "actor_id":actor_id,
        "judgment_code":judgment_code,
        "recorded_at":recorded_at,
        "notes_fingerprint":notes_fingerprint,
    }
    return AgentJudgment(
        judgment_id=judgment_id,
        subject_property_id=subject_property_id,
        actor_id=actor_id,
        judgment_code=judgment_code,
        recorded_at=recorded_at,
        notes_fingerprint=notes_fingerprint,
        judgment_fingerprint=_hash(payload),
    )


def make_action_intent(
    *,
    intent_id: str,
    subject_property_id: str,
    action_type: str,
    origin: str,
    target_review_item_id: str | None,
    requested_at: str,
    requested_policy_version: str,
    registry: Mapping[str,object],
) -> ActionIntent:
    if not intent_id.strip() or not subject_property_id.strip():
        raise ValueError("intent_id and subject_property_id required")
    if action_type not in set(registry["policy"]["allowed_action_types"]):
        raise ValueError("unsupported action type")
    if origin not in set(registry["policy"]["allowed_origins"]):
        raise ValueError("unsupported action origin")
    if requested_policy_version!=registry["policy"]["version"]:
        raise ValueError("requested action policy version is not current")
    _parse_ts(requested_at,"action intent requested_at")
    payload={
        "intent_id":intent_id,
        "subject_property_id":subject_property_id,
        "action_type":action_type,
        "origin":origin,
        "target_review_item_id":target_review_item_id,
        "requested_at":requested_at,
        "requested_policy_version":requested_policy_version,
    }
    return ActionIntent(
        intent_id=intent_id,
        subject_property_id=subject_property_id,
        action_type=action_type,
        origin=origin,
        target_review_item_id=target_review_item_id,
        requested_at=requested_at,
        requested_policy_version=requested_policy_version,
        intent_fingerprint=_hash(payload),
    )


def _validate_case(case: SellerIntelligenceCase) -> None:
    _validate_fp(case.case_fingerprint,"M11 case fingerprint")
    if case.output_tier!="INTERNAL":
        raise ValueError("M12-001 requires INTERNAL Seller Intelligence case")
    if case.public_eligible is not False:
        raise ValueError("M12-001 rejects public-eligible Seller Intelligence case")
    if case.external_action_capability!="NONE":
        raise ValueError("M12-001 rejects case with external action capability")


def _target_review(case: SellerIntelligenceCase, review_item_id: str | None):
    if review_item_id is None:
        return None
    rows=[x for x in case.review_items if x.review_item_id==review_item_id]
    if len(rows)!=1:
        raise ValueError("target review item must resolve exactly once")
    return rows[0]


def _validate_proposal_fields(proposal: GovernedActionProposal, registry: Mapping[str,object]) -> None:
    overlap=set(asdict(proposal)) & set(registry["prohibited_output_fields"])
    if overlap:
        raise ValueError(f"prohibited M12-001 proposal fields present: {sorted(overlap)}")


def build_governed_action_proposal(
    *,
    proposal_id: str,
    case: SellerIntelligenceCase,
    m11_release_certified: bool,
    m11_release_evidence_fingerprint: str,
    m11_release_certification_root: str,
    listing_context: ListingContext,
    intent: ActionIntent,
    registry: Mapping[str,object],
    agent_judgment: AgentJudgment | None = None,
) -> GovernedActionProposal:
    if not proposal_id.strip():
        raise ValueError("proposal_id required")
    _validate_case(case)
    if m11_release_certified is not True:
        raise ValueError("released certified M11 baseline required")
    _validate_fp(m11_release_evidence_fingerprint,"M11 release evidence fingerprint")
    expected_root=str(registry["released_m11"]["certification_root"])
    if m11_release_certification_root!=expected_root:
        raise ValueError("M11 release certification root mismatch")
    _validate_fp(m11_release_certification_root,"M11 release certification root")

    subject=case.subject_property_id
    if listing_context.subject_property_id!=subject or intent.subject_property_id!=subject:
        raise ValueError("M12-001 property lineage mismatch")
    if listing_context.freshness_state!=registry["policy"]["current_freshness_state"]:
        raise ValueError("listing context must remain CURRENT")
    if intent.requested_policy_version!=registry["policy"]["version"]:
        raise ValueError("action intent policy version is stale")
    if intent.action_type not in set(registry["policy"]["allowed_action_types"]):
        raise ValueError("unsupported action type")
    if intent.origin not in set(registry["policy"]["allowed_origins"]):
        raise ValueError("unsupported action origin")

    target=_target_review(case,intent.target_review_item_id)
    reviewable=set(registry["policy"]["reviewable_statuses"])
    reason_codes=[]
    lineage={
        case.case_fingerprint,
        listing_context.context_fingerprint,
        listing_context.source_fingerprint,
        intent.intent_fingerprint,
        m11_release_evidence_fingerprint,
        m11_release_certification_root,
    }

    if intent.origin=="SYSTEM_SIGNAL":
        if target is None:
            raise ValueError("SYSTEM_SIGNAL proposal requires target review item")
        if target.status not in reviewable:
            raise ValueError("SYSTEM_SIGNAL target review item is not current/reviewable")
        reason_codes.append("CURRENT_REVIEW_ITEM")
        lineage.add(target.review_item_fingerprint)
        lineage.add(target.source_event_fingerprint)
        if agent_judgment is not None:
            raise ValueError("SYSTEM_SIGNAL must not consume agent judgment")
    else:
        if agent_judgment is None:
            raise ValueError("AGENT_REQUEST proposal requires agent judgment")
        if agent_judgment.subject_property_id!=subject:
            raise ValueError("agent judgment property mismatch")
        reason_codes.append(agent_judgment.judgment_code)
        lineage.add(agent_judgment.judgment_fingerprint)
        lineage.add(agent_judgment.notes_fingerprint)
        if target is not None:
            if target.status not in reviewable:
                raise ValueError("target review item is not current/reviewable")
            reason_codes.append("CURRENT_REVIEW_ITEM")
            lineage.add(target.review_item_fingerprint)
            lineage.add(target.source_event_fingerprint)

    limitations=set(case.limitations)
    limitations.update({
        "PROPOSAL_ONLY",
        "NO_APPROVAL_OR_AUTHORIZATION",
        "NO_EXECUTION_SIDE_EFFECT",
        "NO_SYSTEM_DETERMINED_PRICE_OR_TERMS",
    })
    prerequisites=tuple(sorted(set(registry["required_prerequisites"])))
    policy_fp=policy_fingerprint(registry)
    lineage.add(policy_fp)
    lineage_tuple=tuple(sorted(lineage))
    state=registry["proposal_state"]

    payload={
        "proposal_id":proposal_id,
        "subject_property_id":subject,
        "listing_id":listing_context.listing_id,
        "action_type":intent.action_type,
        "origin":intent.origin,
        "target_review_item_id":intent.target_review_item_id,
        "reason_codes":tuple(sorted(set(reason_codes))),
        "prerequisites":prerequisites,
        "limitations":tuple(sorted(limitations)),
        "source_case_fingerprint":case.case_fingerprint,
        "listing_context_fingerprint":listing_context.context_fingerprint,
        "intent_fingerprint":intent.intent_fingerprint,
        "agent_judgment_fingerprint":agent_judgment.judgment_fingerprint if agent_judgment else None,
        "m11_release_evidence_fingerprint":m11_release_evidence_fingerprint,
        "m11_release_certification_root":m11_release_certification_root,
        "policy_version":registry["policy"]["version"],
        "policy_fingerprint":policy_fp,
        "lineage_fingerprints":lineage_tuple,
        "proposal_status":state["proposal_status"],
        "approval_state":state["approval_state"],
        "authorization_state":state["authorization_state"],
        "schedule_state":state["schedule_state"],
        "queue_state":state["queue_state"],
        "execution_state":state["execution_state"],
        "publication_state":state["publication_state"],
        "transmission_state":state["transmission_state"],
        "requires_human_approval":True,
        "public_eligible":False,
        "external_action_capability":"NONE",
    }
    proposal=GovernedActionProposal(
        **payload,
        proposal_fingerprint=_hash(payload),
    )
    _validate_proposal_fields(proposal,registry)
    return proposal
