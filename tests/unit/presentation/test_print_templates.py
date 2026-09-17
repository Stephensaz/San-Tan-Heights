from pathlib import Path

import pytest

from src.presentation.pdf import AgentPdfDocument, PdfTemplateFoundation, PdfTemplateRegistry, PublicPdfDocument, SellerPdfDocument
from src.presentation.printing import PrintTemplateRegistry, PrintTemplateRuntime

ROOT = Path(__file__).resolve().parents[3]
PDF_REGISTRY = ROOT / "registries" / "presentation" / "pdf-template-v1.0.yaml"
PRINT_REGISTRY = ROOT / "registries" / "presentation" / "print-template-v1.0.yaml"


def runtime():
    return PrintTemplateRuntime(PrintTemplateRegistry.load(PRINT_REGISTRY))


def pdf_plan(*section_ids):
    foundation = PdfTemplateFoundation(PdfTemplateRegistry.load(PDF_REGISTRY))
    return foundation.plan(section_ids)


def common_kwargs(template):
    return dict(
        property_id="11111111-1111-1111-1111-111111111111",
        address="123 Example St",
        community="San Tan Heights",
        phase="B-3",
        builder="Example Builder",
        floor_plan="Plan 1",
        verified_through="2026-09-17T17:00:00Z",
        market_data_through=None,
        builder_data_through=None,
        summary=(),
        sections=(),
        disclaimers=(),
        template=template,
    )


def test_print_registry_is_locked_and_fail_closed():
    registry = PrintTemplateRegistry.load(PRINT_REGISTRY)
    assert registry.status == "LOCKED"
    assert dict(registry.audiences) == {
        "AGENT": "agent-print-v1",
        "SELLER": "seller-print-v1",
        "PUBLIC": "public-print-v1",
    }
    assert registry.rules["preserve_semantic_order"] is True
    assert registry.rules["allow_content_omission"] is False
    assert registry.rules["allow_audience_reclassification"] is False
    assert registry.rules["allow_print_specific_fact_changes"] is False


def test_print_runtime_infers_audience_from_certified_document_type():
    plan = pdf_plan()
    agent = AgentPdfDocument(
        **common_kwargs(plan), snapshot_id="snapshot-1", dependency_manifest_hash="manifest-1"
    )
    seller = SellerPdfDocument(**common_kwargs(plan))
    public = PublicPdfDocument(**common_kwargs(plan))

    assert runtime().plan(agent).audience == "AGENT"
    assert runtime().plan(seller).audience == "SELLER"
    assert runtime().plan(public).audience == "PUBLIC"
    assert runtime().plan(public).template_key == "public-print-v1"


def test_print_plan_preserves_pdf_semantic_order_and_letter_geometry():
    plan = pdf_plan()
    document = PublicPdfDocument(**common_kwargs(plan))
    print_plan = runtime().plan(document)
    assert print_plan.semantic_order == document.template.semantic_order
    assert print_plan.page.size == "LETTER"
    assert print_plan.page.width_pt == 612.0
    assert print_plan.page.height_pt == 792.0
    assert print_plan.repeat_header is True
    assert print_plan.repeat_footer is True
    assert print_plan.keep_section_heading_with_first_block is True
    assert print_plan.avoid_card_split is True


def test_print_runtime_rejects_non_certified_document_objects():
    with pytest.raises(ValueError, match="certified Agent, Seller, or Public PDF document"):
        runtime().plan(object())


def test_print_runtime_rejects_semantic_order_mismatch():
    document = PublicPdfDocument(**common_kwargs(pdf_plan("unexpected-section")))
    with pytest.raises(ValueError, match="section order does not match"):
        runtime().plan(document)


def test_print_plan_fingerprint_is_deterministic_and_bound_to_source_document():
    plan = pdf_plan()
    document = PublicPdfDocument(**common_kwargs(plan))
    first = runtime().plan(document)
    second = runtime().plan(document)
    assert first.fingerprint == second.fingerprint
    assert first.source_document_fingerprint == document.fingerprint
    assert len(first.fingerprint) == 64
