from pathlib import Path

import pytest

from src.presentation.agent import AgentCardView, AgentFindingView, AgentReportView, AgentSectionView
from src.presentation.audience import AudiencePresentationPolicies
from src.presentation.evidence import EvidenceDisclosureBuilder
from src.presentation.package import PresentationAudience
from src.presentation.public import PublicCardView, PublicFindingView, PublicReportView, PublicSectionView
from src.presentation.seller import SellerCardView, SellerFindingView, SellerReportView, SellerSectionView

ROOT = Path(__file__).resolve().parents[3]


def builder():
    return EvidenceDisclosureBuilder(AudiencePresentationPolicies.from_repository(ROOT))


def agent_report():
    finding = AgentFindingView(
        finding_id="finding-1",
        finding_type="CANONICAL_PHASE",
        label="Community Phase",
        display_text="B-3",
        status_label="Verified",
        confidence_label="High confidence",
        limitation="Based on governed recorded evidence.",
        source_snapshot_id="22222222-2222-2222-2222-222222222222",
        semantic_fingerprint="a" * 64,
    )
    card = AgentCardView("card-1", "EVIDENCE_CARD", "Evidence", None, "Verified", (finding,))
    section = AgentSectionView("evidence", "Evidence", None, (card,))
    return AgentReportView(
        property_id="11111111-1111-1111-1111-111111111111",
        address="123 Example St",
        community="San Tan Heights",
        phase="B-3",
        builder=None,
        floor_plan=None,
        verified_through="2026-09-17T16:00:00Z",
        market_data_through=None,
        builder_data_through=None,
        summary=(),
        sections=(section,),
        disclaimers=("Governed evidence disclosure.",),
        snapshot_id="22222222-2222-2222-2222-222222222222",
        dependency_manifest_hash="b" * 64,
    )


def seller_report():
    finding = SellerFindingView(
        finding_id="finding-1",
        finding_type="CANONICAL_PHASE",
        label="Community Phase",
        display_text="B-3",
        status_label="Verified",
        confidence_label="Verified from available records",
        limitation="Based on governed recorded evidence.",
    )
    card = SellerCardView("card-1", "EVIDENCE_CARD", "Evidence", None, "Verified", (finding,))
    section = SellerSectionView("evidence", "Evidence", None, (card,))
    return SellerReportView(
        property_id="11111111-1111-1111-1111-111111111111",
        address="123 Example St",
        community="San Tan Heights",
        phase="B-3",
        builder=None,
        floor_plan=None,
        verified_through="2026-09-17T16:00:00Z",
        market_data_through=None,
        builder_data_through=None,
        summary=(),
        sections=(section,),
        disclaimers=("Governed evidence disclosure.",),
    )


def public_report():
    finding = PublicFindingView(
        finding_id="finding-1",
        finding_type="CANONICAL_PHASE",
        label="Community Phase",
        display_text="B-3",
        status_label="Verified",
        confidence_label=None,
        limitation="Based on available governed records.",
    )
    card = PublicCardView("card-1", "EVIDENCE_CARD", "Evidence", None, "Verified", (finding,))
    section = PublicSectionView("evidence", "Evidence", None, (card,))
    return PublicReportView(
        property_id="11111111-1111-1111-1111-111111111111",
        address="123 Example St",
        community="San Tan Heights",
        phase="B-3",
        builder=None,
        floor_plan=None,
        verified_through="2026-09-17T16:00:00Z",
        market_data_through=None,
        builder_data_through=None,
        summary=(),
        sections=(section,),
        disclaimers=("Governed evidence disclosure.",),
    )


def test_agent_disclosure_uses_detailed_policy_and_preserves_lineage():
    disclosure = builder().build(agent_report(), audience=PresentationAudience.AGENT)
    assert disclosure.evidence_depth == "DETAILED"
    assert disclosure.items[0].source_snapshot_id == "22222222-2222-2222-2222-222222222222"
    assert disclosure.items[0].semantic_fingerprint == "a" * 64


def test_seller_disclosure_uses_standard_policy_without_agent_lineage():
    disclosure = builder().build(seller_report(), audience=PresentationAudience.SELLER)
    assert disclosure.evidence_depth == "STANDARD"
    assert disclosure.items[0].source_snapshot_id is None
    assert disclosure.items[0].semantic_fingerprint is None
    assert disclosure.items[0].limitation == "Based on governed recorded evidence."


def test_public_disclosure_uses_light_policy_without_agent_lineage():
    disclosure = builder().build(public_report(), audience=PresentationAudience.PUBLIC)
    assert disclosure.evidence_depth == "LIGHT"
    assert disclosure.items[0].source_snapshot_id is None
    assert disclosure.items[0].semantic_fingerprint is None
    assert disclosure.items[0].confidence_label is None


def test_disclosure_rejects_audience_view_mismatch():
    with pytest.raises(ValueError, match="does not match audience"):
        builder().build(agent_report(), audience=PresentationAudience.PUBLIC)


def test_disclosure_fingerprint_is_deterministic_and_preserves_order():
    first = builder().build(agent_report(), audience=PresentationAudience.AGENT)
    second = builder().build(agent_report(), audience=PresentationAudience.AGENT)
    assert first.fingerprint == second.fingerprint
    assert len(first.fingerprint) == 64
    assert [item.finding_id for item in first.items] == ["finding-1"]
