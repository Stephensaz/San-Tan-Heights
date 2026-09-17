import copy

import pytest

from src.presentation.seller import SellerReportExperience


def sample_payload():
    return {
        "metadata": {
            "report_variant": "SELLER",
            "verified_through": "2026-09-17T15:00:00Z",
            "market_data_through": "2026-09-16T23:59:59Z",
            "builder_data_through": None,
        },
        "property_identity": {
            "property_id": "11111111-1111-1111-1111-111111111111",
            "address": "123 Example St",
            "community": "San Tan Heights",
            "phase": "B-3",
            "builder": "Example Builder",
            "floor_plan": "Plan 1",
        },
        "summary": ["Seller-friendly governed summary text."],
        "sections": [
            {"section_id": "summary", "title": "Summary", "order": 1, "card_ids": ["card-1"], "summary": None},
            {"section_id": "evidence", "title": "Evidence", "order": 2, "card_ids": ["card-2"], "summary": "Evidence detail"},
        ],
        "cards": [
            {"card_id": "card-1", "card_type": "SUMMARY_CARD", "section_id": "summary", "title": "Summary", "body": None, "finding_ids": ["finding-1"], "status_label": None},
            {"card_id": "card-2", "card_type": "EVIDENCE_CARD", "section_id": "evidence", "title": "Evidence", "body": "Source-backed detail", "finding_ids": ["finding-2"], "status_label": "Verified"},
        ],
        "findings": [
            {
                "finding_id": "finding-1",
                "finding_type": "CANONICAL_PHASE",
                "label": "Community Phase",
                "display_text": "B-3",
                "section_id": "summary",
                "status_label": "Verified",
                "confidence_label": "High confidence",
                "limitation": None,
                "source_snapshot_id": "22222222-2222-2222-2222-222222222222",
                "semantic_fingerprint": "a" * 64,
            },
            {
                "finding_id": "finding-2",
                "finding_type": "ROAD_ADJACENCY",
                "label": "Nearby Road Relationship",
                "display_text": "No governed road-adjacency exception noted.",
                "section_id": "evidence",
                "status_label": "Verified",
                "confidence_label": "Verified from available records",
                "limitation": "Based on governed source geometry.",
                "source_snapshot_id": "22222222-2222-2222-2222-222222222222",
                "semantic_fingerprint": "b" * 64,
            },
        ],
        "disclaimers": ["Information is based on governed records and may change as sources update."],
    }


def test_seller_experience_preserves_seller_content_and_order():
    view = SellerReportExperience().build(sample_payload())
    assert [section.section_id for section in view.sections] == ["summary", "evidence"]
    assert view.sections[0].cards[0].findings[0].label == "Community Phase"
    assert view.sections[1].cards[0].findings[0].limitation == "Based on governed source geometry."
    assert len(view.fingerprint) == 64


def test_seller_view_omits_agent_only_finding_lineage_fields():
    view = SellerReportExperience().build(sample_payload())
    finding = view.sections[0].cards[0].findings[0]
    assert not hasattr(finding, "source_snapshot_id")
    assert not hasattr(finding, "semantic_fingerprint")


def test_seller_experience_fingerprint_is_deterministic():
    builder = SellerReportExperience()
    assert builder.build(sample_payload()).fingerprint == builder.build(copy.deepcopy(sample_payload())).fingerprint


def test_seller_experience_rejects_non_seller_payload():
    payload = sample_payload()
    payload["metadata"]["report_variant"] = "AGENT"
    with pytest.raises(ValueError, match="requires a SELLER"):
        SellerReportExperience().build(payload)


def test_seller_experience_rejects_broken_card_reference():
    payload = sample_payload()
    payload["sections"][0]["card_ids"] = ["missing-card"]
    with pytest.raises(ValueError, match="unknown card"):
        SellerReportExperience().build(payload)


def test_seller_experience_rejects_broken_finding_reference():
    payload = sample_payload()
    payload["cards"][0]["finding_ids"] = ["missing-finding"]
    with pytest.raises(ValueError, match="unknown finding"):
        SellerReportExperience().build(payload)
