from pathlib import Path

import pytest

from src.presentation.pdf import PdfTemplateFoundation, PdfTemplateRegistry

ROOT = Path(__file__).resolve().parents[3]
REGISTRY = ROOT / "registries" / "presentation" / "pdf-template-v1.0.yaml"


def foundation():
    return PdfTemplateFoundation(PdfTemplateRegistry.load(REGISTRY))


def test_pdf_template_uses_locked_letter_geometry():
    plan = foundation().plan(("header", "summary", "evidence"))
    assert plan.page.size == "LETTER"
    assert plan.page.width_pt == 612.0
    assert plan.page.height_pt == 792.0
    assert plan.page.body_width_pt == 504.0
    assert plan.page.body_height_pt == 618.0


def test_pdf_template_preserves_semantic_order_exactly():
    order = ("header", "summary", "property-dna", "evidence", "freshness")
    plan = foundation().plan(order)
    assert plan.semantic_order == order


def test_pdf_template_locks_header_footer_and_section_flow_rules():
    plan = foundation().plan(("summary", "evidence"))
    assert plan.repeat_header is True
    assert plan.repeat_footer is True
    assert plan.keep_section_heading_with_first_block is True
    assert plan.allow_section_body_split is True


def test_pdf_template_rejects_blank_or_duplicate_semantic_ids():
    f = foundation()
    with pytest.raises(ValueError, match="cannot be blank"):
        f.plan(("summary", " "))
    with pytest.raises(ValueError, match="must be unique"):
        f.plan(("summary", "summary"))


def test_pdf_template_fingerprint_is_deterministic():
    first = foundation().plan(("summary", "evidence"))
    second = foundation().plan(("summary", "evidence"))
    assert first.fingerprint == second.fingerprint
    assert len(first.fingerprint) == 64
