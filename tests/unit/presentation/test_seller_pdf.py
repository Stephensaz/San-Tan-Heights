from pathlib import Path

import pytest

from src.presentation.pdf import PdfTemplateFoundation, PdfTemplateRegistry, SellerPdfComposer
from src.presentation.seller import SellerCardView, SellerFindingView, SellerReportView, SellerSectionView

ROOT = Path(__file__).resolve().parents[3]
PDF_REGISTRY = ROOT / "registries" / "presentation" / "pdf-template-v1.0.yaml"


def composer():
    return SellerPdfComposer(PdfTemplateFoundation(PdfTemplateRegistry.load(PDF_REGISTRY)))


def report():
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
    section = SellerSectionView("evidence", "Evidence", "Seller-friendly evidence", (card,))
    return SellerReportView(
        property_id="11111111-1111-1111-1111-111111111111",
        address="123 Example St",
        community="San Tan Heights",
        phase="B-3",
        builder="Example Builder",
        floor_plan="Plan 1",
        verified_through="2026-09-17T17:00:00Z",
        market_data_through=None,
        builder_data_through=None,
        summary=("Governed Seller summary.",),
        sections=(section,),
        disclaimers=("Seller-use governed report.",),
    )


def test_seller_pdf_preserves_seller_safe_content_without_agent_lineage():
    document = composer().compose(report())
    finding = document.sections[0].cards[0].findings[0]
    assert finding.label == "Community Phase"
    assert finding.confidence_label == "Verified from available records"
    assert not hasattr(finding, "source_snapshot_id")
    assert not hasattr(finding, "semantic_fingerprint")
    assert not hasattr(document, "snapshot_id")
    assert not hasattr(document, "dependency_manifest_hash")


def test_seller_pdf_uses_locked_letter_template_and_order():
    document = composer().compose(report())
    assert document.template.page.size == "LETTER"
    assert document.template.semantic_order == ("evidence",)
    assert document.disclaimers == ("Seller-use governed report.",)


def test_seller_pdf_rejects_non_seller_report_objects():
    with pytest.raises(ValueError, match="requires a SellerReportView"):
        composer().compose(object())


def test_seller_pdf_fingerprint_is_deterministic():
    first = composer().compose(report())
    second = composer().compose(report())
    assert first.fingerprint == second.fingerprint
    assert len(first.fingerprint) == 64
