from dataclasses import fields

import pytest

from src.seller_intelligence.workspace import ReviewItem, SellerIntelligenceCase
from src.listing_execution.action_planning import (
    build_governed_action_proposal,
    load_action_proposal_registry,
    make_action_intent,
    make_agent_judgment,
    make_listing_context,
    policy_fingerprint,
)

R="registries/listing_execution/m12-001-action-proposal-v1.0.yaml"
M11_ROOT="8c5c656934909c10c3c5bc52ae9d12b3c646348686f3d1d787a9b0b067ce6ccf"
M11_EVIDENCE_FP="a"*64


def reg():
    return load_action_proposal_registry(R)


def review(status="PENDING"):
    return ReviewItem(
        review_item_id="REVIEW-1",
        source_event_fingerprint="1"*64,
        snapshot_id="S-1",
        status=status,
        reasons=("COMPETITIVE_PRESSURE:CHANGED",),
        acknowledged_by_decision_id=None,
        resolved_by_decision_id=None,
        review_item_fingerprint="2"*64,
    )


def case(status="PENDING", *, public=False, action="NONE"):
    return SellerIntelligenceCase(
        case_id="CASE-1",
        subject_property_id="SUBJECT-1",
        current_artifacts=(),
        superseded_artifacts=(),
        review_items=(review(status),),
        human_decisions=(),
        limitations=("WEEK_OVER_WEEK_DIRECTION:MISSING",),
        next_safe_step="REVIEW_PENDING_ITEM",
        output_tier="INTERNAL",
        public_eligible=public,
        external_action_capability=action,
        case_fingerprint="3"*64,
    )


def context(**overrides):
    kw=dict(
        listing_id="LISTING-1",
        subject_property_id="SUBJECT-1",
        listing_status="ACTIVE",
        freshness_state="CURRENT",
        observed_at="2026-09-18T09:00:00-07:00",
        source_fingerprint="4"*64,
        registry=reg(),
    )
    kw.update(overrides)
    return make_listing_context(**kw)


def system_intent(**overrides):
    kw=dict(
        intent_id="INTENT-1",
        subject_property_id="SUBJECT-1",
        action_type="REVIEW_LISTING_POSITIONING",
        origin="SYSTEM_SIGNAL",
        target_review_item_id="REVIEW-1",
        requested_at="2026-09-18T09:05:00-07:00",
        requested_policy_version="LISTING-ACTION-PROPOSAL-v1.0",
        registry=reg(),
    )
    kw.update(overrides)
    return make_action_intent(**kw)


def judgment(**overrides):
    kw=dict(
        judgment_id="J-1",
        subject_property_id="SUBJECT-1",
        actor_id="AGENT-1",
        judgment_code="AGENT_REVIEW_REQUEST",
        recorded_at="2026-09-18T09:04:00-07:00",
        notes_fingerprint="5"*64,
        registry=reg(),
    )
    kw.update(overrides)
    return make_agent_judgment(**kw)


def proposal(**overrides):
    kw=dict(
        proposal_id="PROP-1",
        case=case(),
        m11_release_certified=True,
        m11_release_evidence_fingerprint=M11_EVIDENCE_FP,
        m11_release_certification_root=M11_ROOT,
        listing_context=context(),
        intent=system_intent(),
        registry=reg(),
    )
    kw.update(overrides)
    return build_governed_action_proposal(**kw)


def test_system_signal_proposal_is_deterministic():
    assert proposal().proposal_fingerprint==proposal().proposal_fingerprint


def test_proposal_is_only_proposed_and_never_authorized_or_executable():
    p=proposal()
    assert p.proposal_status=="PROPOSED"
    assert p.approval_state=="NOT_APPROVED"
    assert p.authorization_state=="NOT_AUTHORIZED"
    assert p.schedule_state=="NOT_SCHEDULED"
    assert p.queue_state=="NOT_QUEUED"
    assert p.execution_state=="NOT_EXECUTABLE"
    assert p.publication_state=="NOT_PUBLISHED"
    assert p.transmission_state=="NOT_TRANSMITTED"
    assert p.requires_human_approval is True
    assert p.public_eligible is False
    assert p.external_action_capability=="NONE"


def test_exact_lineage_contains_m11_case_release_listing_intent_policy_and_review():
    p=proposal()
    required={
        "3"*64,
        M11_EVIDENCE_FP,
        M11_ROOT,
        context().context_fingerprint,
        context().source_fingerprint,
        system_intent().intent_fingerprint,
        "1"*64,
        "2"*64,
        policy_fingerprint(reg()),
    }
    assert required.issubset(set(p.lineage_fingerprints))


def test_limitations_and_prerequisites_remain_explicit():
    p=proposal()
    assert "WEEK_OVER_WEEK_DIRECTION:MISSING" in p.limitations
    assert "PROPOSAL_ONLY" in p.limitations
    assert "NO_SYSTEM_DETERMINED_PRICE_OR_TERMS" in p.limitations
    assert set(p.prerequisites)=={
        "HUMAN_APPROVAL_REQUIRED",
        "M12_002_AUTHORIZATION_REQUIRED",
        "AUTHORITY_REVALIDATION_REQUIRED_BEFORE_EXECUTION",
    }


def test_system_signal_requires_current_review_item():
    with pytest.raises(ValueError,match="requires target review item"):
        proposal(intent=system_intent(target_review_item_id=None))


@pytest.mark.parametrize("status",["RESOLVED","SUPERSEDED"])
def test_resolved_or_superseded_review_item_fails_closed(status):
    with pytest.raises(ValueError,match="not current/reviewable"):
        proposal(case=case(status))


def test_agent_request_requires_agent_judgment():
    i=system_intent(origin="AGENT_REQUEST",target_review_item_id=None)
    with pytest.raises(ValueError,match="requires agent judgment"):
        proposal(intent=i)


def test_agent_request_preserves_human_judgment_as_lineage_without_interpreting_notes():
    i=system_intent(
        origin="AGENT_REQUEST",
        action_type="REVIEW_LISTING_TERMS",
        target_review_item_id=None,
    )
    j=judgment(judgment_code="SELLER_DIRECTION_RECORDED")
    p=proposal(intent=i,agent_judgment=j)
    assert p.reason_codes==("SELLER_DIRECTION_RECORDED",)
    assert j.judgment_fingerprint in p.lineage_fingerprints
    assert j.notes_fingerprint in p.lineage_fingerprints
    assert p.agent_judgment_fingerprint==j.judgment_fingerprint


def test_system_signal_rejects_agent_judgment():
    with pytest.raises(ValueError,match="must not consume agent judgment"):
        proposal(agent_judgment=judgment())


def test_stale_listing_context_fails_closed():
    with pytest.raises(ValueError,match="must be CURRENT"):
        context(freshness_state="STALE")


def test_stale_policy_version_fails_closed():
    with pytest.raises(ValueError,match="not current"):
        system_intent(requested_policy_version="LISTING-ACTION-PROPOSAL-v0.9")


def test_wrong_m11_release_root_fails_closed():
    with pytest.raises(ValueError,match="root mismatch"):
        proposal(m11_release_certification_root="0"*64)


def test_uncertified_m11_release_fails_closed():
    with pytest.raises(ValueError,match="released certified M11 baseline required"):
        proposal(m11_release_certified=False)


def test_property_mismatch_fails_closed():
    bad=context(subject_property_id="OTHER")
    with pytest.raises(ValueError,match="property lineage mismatch"):
        proposal(listing_context=bad)


def test_public_or_external_action_case_fails_closed():
    with pytest.raises(ValueError,match="public-eligible"):
        proposal(case=case(public=True))
    with pytest.raises(ValueError,match="external action capability"):
        proposal(case=case(action="EXECUTE"))


def test_unsupported_action_type_is_rejected_before_proposal():
    with pytest.raises(ValueError,match="unsupported action type"):
        system_intent(action_type="CHANGE_LIST_PRICE")


def test_proposal_dto_has_no_price_terms_payload_approval_execution_or_side_effect_fields():
    names={x.name for x in fields(type(proposal()))}
    assert names.isdisjoint(set(reg()["prohibited_output_fields"]))
