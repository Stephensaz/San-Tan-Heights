from pathlib import Path

import pytest

from src.presentation.agent import AgentCardView, AgentFindingView, AgentReportView, AgentSectionView
from src.presentation.pdf import AgentPdfComposer, PdfTemplateFoundation, PdfTemplateRegistry

ROOT = Path(__file__).resolve().parents[3]
PDF_REGISTRY = ROOT / "registries" / "presentation" / "pdf-template-v1.0.yaml"


def composer():
    return AgentPdfComposer(PdfTemplateFoundation(PdfTemplateRegistry.load(PDF_REGISTRY)))


def report():
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
    section = AgentSectionView("evidence", "Evidence", "Detailed source-backed evidence", (card,))
    return AgentReportView(
        property_id="11111111-1111-1111-1111-111111111111",
        address="123 Example St",
        community="San Tan Heights",
        phase="B-3",
        builder="Example Builder",
        floor_plan="Plan 1",
        verified_through="2026-09-17T17:00:00Z",
        market_data_through="2026-09-16T23:59:59Z",
        builder_data_through=None,
        summary=("Governed Agent summary.",),
        sections=(section,),
        disclaimers=("Agent-use governed report.",),
        snapshot_id="22222222-2222-2222-2222-222222222222",
        dependency_manifest_hash="b" * 64,
    )


def test_agent_pdf_preserves_agent_lineage_and_governed_text():
    document = composer().compose(report())
    finding = document.sections[0].cards[0].findings[0]
    assert finding.label == "Community Phase"
    assert finding.display_text == "B-3"
    assert finding.source_snapshot_id == "22222222-2222-2222-2222-222222222222"
    assert finding.semantic_fingerprint == "a" * 64
    assert document.snapshot_id == "22222222-2222-2222-2222-222222222222"


def test_agent_pdf_uses_locked_pdf_template_and_section_order():
    document = composer().compose(report())
    assert document.template.page.size == "LETTER"
    assert document.template.semantic_order == ("evidence",)
    assert [section.section_id for section in document.sections] == ["evidence"]


def test_agent_pdf_does_not_drop_disclaimers_or_freshness():
    document = composer().compose(report())
    assert document.disclaimers == ("Agent-use governed report.",)
    assert document.verified_through == "2026-09-17T17:00:00Z"
    assert document.market_data_through == "2026-09-16T23:59:59Z"


def test_agent_pdf_rejects_non_agent_report_objects():
    with pytest.raises(ValueError, match="requires an AgentReportView"):
        composer().compose(object())


def test_agent_pdf_fingerprint_is_deterministic():
    first = composer().compose(report())
    second = composer().compose(report())
    assert first.fingerprint == second.fingerprint
    assert len(first.fingerprint) == 64
