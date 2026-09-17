from pathlib import Path

import pytest

from src.presentation.diagram import (
    DiagramAccessibilityLayer,
    DiagramEntity,
    DiagramGrammarRegistry,
    DiagramGrammarRuntime,
    DiagramGrammarSpec,
    DiagramRelationship,
    LotContextDiagramRenderer,
)
from src.presentation.tokens import DesignTokenRegistry

ROOT = Path(__file__).resolve().parents[3]
GRAMMAR = ROOT / "registries" / "presentation" / "diagram-grammar-v1.0.yaml"
TOKENS = ROOT / "registries" / "presentation" / "design-tokens-v1.0.yaml"


def render_diagram():
    renderer = LotContextDiagramRenderer(
        grammar=DiagramGrammarRuntime(DiagramGrammarRegistry.load(GRAMMAR)),
        tokens=DesignTokenRegistry.load(TOKENS),
    )
    spec = DiagramGrammarSpec(
        diagram_id="lot-context",
        entities=(
            DiagramEntity("subject-lot", "SUBJECT_LOT", "Subject Homesite", "finding-subject"),
            DiagramEntity("rear-tract", "COMMON_TRACT", "Recorded Tract", "finding-tract"),
            DiagramEntity("front-road", "ROAD", "Internal Road", "finding-road"),
            DiagramEntity("side-space", "OPEN_SPACE", "Open Space", "finding-space"),
        ),
        relationships=(
            DiagramRelationship("z-rear", "BACKS_TO", "subject-lot", "rear-tract", "finding-tract"),
            DiagramRelationship("a-front", "FRONTS", "subject-lot", "front-road", "finding-road"),
            DiagramRelationship("m-side", "SIDES_TO", "subject-lot", "side-space", "finding-space"),
        ),
    )
    return renderer.render(spec)


def test_accessibility_layer_produces_deterministic_alt_and_long_description():
    layer = DiagramAccessibilityLayer()
    first = layer.build(render_diagram())
    second = layer.build(render_diagram())
    assert first.short_description == "Schematic relationship diagram for Subject Homesite."
    assert "Front relationship: Internal Road." in first.long_description
    assert "Rear relationship: Recorded Tract." in first.long_description
    assert first.fingerprint == second.fingerprint
    assert len(first.fingerprint) == 64


def test_accessibility_reading_order_is_semantic_not_svg_draw_order():
    view = DiagramAccessibilityLayer().build(render_diagram())
    assert [item.semantic_zone for item in view.reading_order] == ["FRONT", "REAR", "SIDE_LEFT"]
    assert view.nonvisual_equivalent[0] == "Subject: Subject Homesite."
    assert view.nonvisual_equivalent[-1] == view.notice


def test_accessible_svg_has_title_desc_and_aria_linkage():
    view = DiagramAccessibilityLayer().build(render_diagram())
    assert 'aria-labelledby="lot-context-title lot-context-desc"' in view.accessible_svg
    assert '<title id="lot-context-title">' in view.accessible_svg
    assert '<desc id="lot-context-desc">' in view.accessible_svg


def test_accessibility_output_does_not_expose_source_finding_ids_to_consumers():
    view = DiagramAccessibilityLayer().build(render_diagram())
    assert "finding-road" not in view.short_description
    assert "finding-road" not in view.long_description
    assert "finding-road" not in view.accessible_svg
    assert all("finding-" not in line for line in view.nonvisual_equivalent)
    assert view.reading_order[0].source_finding_id == "finding-road"


def test_accessibility_layer_does_not_invent_compass_or_distance_claims():
    view = DiagramAccessibilityLayer().build(render_diagram())
    text = " ".join((view.short_description, view.long_description, *view.nonvisual_equivalent)).lower()
    for prohibited in ("north", "south", "east", "west", "feet", "miles"):
        assert prohibited not in text


def test_accessibility_layer_rejects_uncertified_svg_contract():
    render = render_diagram()
    tampered = render.__class__(
        diagram_id=render.diagram_id,
        subject_label=render.subject_label,
        placements=render.placements,
        notice=render.notice,
        svg="<svg></svg>",
    )
    with pytest.raises(ValueError, match="certified renderer contract"):
        DiagramAccessibilityLayer().build(tampered)
