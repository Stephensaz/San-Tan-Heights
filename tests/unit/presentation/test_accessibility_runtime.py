from pathlib import Path

import pytest

from src.presentation.accessibility import AccessibilityRuntimeRegistry, PresentationAccessibilityRuntime
from src.presentation.diagram.accessibility import AccessibleDiagramView
from src.presentation.pdf import PdfTemplateFoundation, PdfTemplateRegistry, PublicPdfDocument
from src.presentation.printing import PrintTemplateRegistry, PrintTemplateRuntime

ROOT = Path(__file__).resolve().parents[3]
PDF_REGISTRY = ROOT / "registries" / "presentation" / "pdf-template-v1.0.yaml"
PRINT_REGISTRY = ROOT / "registries" / "presentation" / "print-template-v1.0.yaml"
ACCESSIBILITY_REGISTRY = ROOT / "registries" / "presentation" / "accessibility-runtime-v1.0.yaml"


def runtime():
    return PresentationAccessibilityRuntime(AccessibilityRuntimeRegistry.load(ACCESSIBILITY_REGISTRY))


def pdf_document(*, address="123 Example St", semantic_order=()):
    template = PdfTemplateFoundation(PdfTemplateRegistry.load(PDF_REGISTRY)).plan(semantic_order)
    return PublicPdfDocument(
        property_id="11111111-1111-1111-1111-111111111111",
        address=address,
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


def accessible_diagram(*, svg=None, nonvisual=None):
    return AccessibleDiagramView(
        diagram_id="diagram-1",
        subject_label="123 Example St",
        short_description="Schematic relationship diagram for 123 Example St.",
        long_description="Schematic relationship diagram for 123 Example St. No verified relationships are shown.",
        reading_order=(),
        nonvisual_equivalent=nonvisual or ("Subject: 123 Example St.", "No verified relationships are shown."),
        notice="No verified relationships are shown.",
        accessible_svg=svg or (
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 500" role="img" '
            'aria-labelledby="diagram-1-title diagram-1-desc">'
            '<title id="diagram-1-title">Schematic relationship diagram</title>'
            '<desc id="diagram-1-desc">No verified relationships are shown.</desc></svg>'
        ),
    )


def test_accessibility_registry_is_locked_and_nonsemantic():
    registry = AccessibilityRuntimeRegistry.load(ACCESSIBILITY_REGISTRY)
    assert registry.status == "LOCKED"
    assert registry.rules["preserve_semantic_order"] is True
    assert registry.rules["allow_accessibility_specific_property_facts"] is False
    assert registry.rules["allow_audience_reclassification"] is False
    assert registry.rules["allow_content_rewriting"] is False


def test_pdf_accessibility_audit_passes_for_valid_certified_document():
    audit = runtime().audit_pdf(pdf_document())
    assert audit.passed is True
    assert audit.issues == ()
    assert len(audit.fingerprint) == 64


def test_pdf_accessibility_audit_fails_blank_identity_text_and_order_mismatch():
    audit = runtime().audit_pdf(pdf_document(address=" ", semantic_order=("missing",)))
    assert audit.passed is False
    assert {issue.code for issue in audit.issues} == {"PROPERTY_IDENTITY_TEXT", "SEMANTIC_ORDER_MISMATCH"}
    with pytest.raises(ValueError, match="accessibility audit failed"):
        runtime().require_pass(audit)


def test_print_accessibility_requires_exact_source_binding():
    document = pdf_document()
    print_runtime = PrintTemplateRuntime(PrintTemplateRegistry.load(PRINT_REGISTRY))
    plan = print_runtime.plan(document)
    audit = runtime().audit_print(document, plan)
    assert audit.passed is True

    other_document = pdf_document(address="456 Other St")
    mismatch = runtime().audit_print(other_document, plan)
    assert mismatch.passed is False
    assert "PRINT_SOURCE_MISMATCH" in {issue.code for issue in mismatch.issues}


def test_diagram_accessibility_requires_nonvisual_equivalent_and_svg_metadata():
    assert runtime().audit_diagram(accessible_diagram()).passed is True

    broken = accessible_diagram(svg="<svg></svg>", nonvisual=(" ",))
    audit = runtime().audit_diagram(broken)
    assert audit.passed is False
    assert {issue.code for issue in audit.issues} == {
        "DIAGRAM_NONVISUAL_EQUIVALENT",
        "DIAGRAM_SVG_METADATA",
    }


def test_accessibility_audit_is_deterministic():
    first = runtime().audit_diagram(accessible_diagram())
    second = runtime().audit_diagram(accessible_diagram())
    assert first.fingerprint == second.fingerprint
