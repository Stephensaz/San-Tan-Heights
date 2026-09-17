from pathlib import Path

import pytest

from src.presentation.audience import AudiencePresentationPolicies
from src.presentation.changes import (
    CertifiedChangeDTO,
    ChangeGroupKey,
    ChangeMateriality,
    ChangeType,
    WhatChangedUi,
)
from src.presentation.package import PresentationAudience

ROOT = Path(__file__).resolve().parents[3]
OLD_FP = "a" * 64
NEW_FP = "b" * 64
DIFF = "c" * 64


def policies():
    return AudiencePresentationPolicies.from_repository(ROOT)


def policy(audience=PresentationAudience.PUBLIC):
    return policies().for_audience(audience)


def change(
    *,
    audience=PresentationAudience.PUBLIC,
    change_type=ChangeType.VALUE_CHANGED,
    materiality=ChangeMateriality.MATERIAL,
    before="Before",
    after="After",
    current_classification="PUBLIC_DATA",
    current_publication_scope="PUBLIC",
    historical_classification="PUBLIC_DATA",
    historical_publication_scope="PUBLIC",
    property_id="property-1",
    change_id="change-1",
    source_diff_hash=DIFF,
    knowledge_change_only=True,
):
    return CertifiedChangeDTO(
        change_id=change_id,
        property_id=property_id,
        audience=audience,
        change_type=change_type,
        finding_key="finding.phase",
        label="Community Phase",
        before=before,
        after=after,
        materiality=materiality,
        detected_at="2026-09-17T23:00:00Z",
        source_diff_hash=source_diff_hash,
        current_classification=current_classification,
        current_publication_scope=current_publication_scope,
        historical_classification=historical_classification,
        historical_publication_scope=historical_publication_scope,
        knowledge_change_only=knowledge_change_only,
    )


def build(*changes, audience=PresentationAudience.PUBLIC, **kwargs):
    return WhatChangedUi().build(
        audience=audience,
        policy=policy(audience),
        property_id="property-1",
        previous_semantic_fingerprint=OLD_FP,
        current_semantic_fingerprint=NEW_FP,
        changes=changes,
        **kwargs,
    )


def test_semantic_changes_are_grouped_deterministically():
    panel = build(
        change(change_type=ChangeType.CORRECTION, change_id="z"),
        change(change_type=ChangeType.NEW_FINDING, change_id="a"),
        change(change_type=ChangeType.EVIDENCE_CHANGED, change_id="e"),
        change(change_type=ChangeType.MARKET_CONTEXT_CHANGED, change_id="m"),
    )
    assert tuple(group.key for group in panel.groups) == (
        ChangeGroupKey.NEWLY_VERIFIED,
        ChangeGroupKey.CORRECTED,
        ChangeGroupKey.EVIDENCE_UPDATED,
        ChangeGroupKey.MARKET_CONTEXT_UPDATED,
    )
    assert panel.title == "What Changed"
    assert len(panel.fingerprint) == 64


def test_wording_and_no_semantic_change_noise_are_omitted():
    assert build(change(change_type=ChangeType.WORDING_ONLY)) is None
    assert build(change(change_type=ChangeType.NO_SEMANTIC_CHANGE)) is None


def test_seller_and_public_omit_detail_only_changes_but_agent_can_show_them():
    detail_public = change(materiality=ChangeMateriality.DETAIL)
    assert build(detail_public) is None

    detail_agent = change(
        audience=PresentationAudience.AGENT,
        materiality=ChangeMateriality.DETAIL,
        current_classification="AGENT_INTERNAL",
        current_publication_scope="AGENT",
        historical_classification="AGENT_INTERNAL",
        historical_publication_scope="AGENT",
    )
    panel = build(detail_agent, audience=PresentationAudience.AGENT)
    assert panel.groups[0].items[0].materiality is ChangeMateriality.DETAIL


def test_same_audience_and_property_identity_are_mandatory():
    with pytest.raises(ValueError, match="audience mismatch"):
        build(change(audience=PresentationAudience.SELLER))
    with pytest.raises(ValueError, match="property identity mismatch"):
        build(change(property_id="other-property"))


def test_source_diff_history_must_be_coherent():
    with pytest.raises(ValueError, match="source diff mismatch"):
        build(change(change_id="1"), change(change_id="2", source_diff_hash="d" * 64))


def test_current_authorization_fails_closed():
    with pytest.raises(ValueError, match="not eligible"):
        build(
            change(
                current_classification="SELLER_DATA",
                current_publication_scope="SELLER",
            )
        )


def test_historical_values_are_redacted_under_current_audience_policy():
    panel = build(
        change(
            before="Private historical value",
            historical_classification="SELLER_DATA",
            historical_publication_scope="SELLER",
        )
    )
    item = panel.groups[0].items[0]
    assert item.before is None
    assert item.historical_value_withheld is True
    assert item.after == "After"


def test_corrections_are_presented_as_corrected_not_refreshes():
    panel = build(change(change_type=ChangeType.CORRECTION))
    assert panel.groups[0].key is ChangeGroupKey.CORRECTED
    assert panel.groups[0].title == "Corrected"


def test_first_report_omits_what_changed_section():
    panel = WhatChangedUi().build(
        audience=PresentationAudience.PUBLIC,
        policy=policy(),
        property_id="property-1",
        previous_semantic_fingerprint=None,
        current_semantic_fingerprint=NEW_FP,
        changes=(),
        has_previous_report=False,
    )
    assert panel is None


def test_change_ui_does_not_expose_cause_or_reverification_claims():
    panel = build(change(knowledge_change_only=True))
    item = panel.groups[0].items[0]
    assert item.knowledge_change_only is True
    assert not hasattr(item, "cause")
    assert not hasattr(item, "reason")
    assert not hasattr(item, "reverified")


def test_identical_semantic_fingerprints_reject_claimed_semantic_changes():
    with pytest.raises(ValueError, match="identical report fingerprints"):
        WhatChangedUi().build(
            audience=PresentationAudience.PUBLIC,
            policy=policy(),
            property_id="property-1",
            previous_semantic_fingerprint=OLD_FP,
            current_semantic_fingerprint=OLD_FP,
            changes=(change(),),
        )


def test_output_fingerprint_is_input_order_independent():
    first = build(change(change_id="b"), change(change_id="a"))
    second = build(change(change_id="a"), change(change_id="b"))
    assert first.fingerprint == second.fingerprint
