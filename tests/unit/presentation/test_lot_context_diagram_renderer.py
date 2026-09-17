from pathlib import Path

import pytest

from src.presentation.diagram import (
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


def renderer():
    return LotContextDiagramRenderer(
        grammar=DiagramGrammarRuntime(DiagramGrammarRegistry.load(GRAMMAR)),
        tokens=DesignTokenRegistry.load(TOKENS),
    )


def sample_spec():
    return DiagramGrammarSpec(
        diagram_id="lot-context",
        entities=(
            DiagramEntity("subject-lot", "SUBJECT_LOT", "Subject Homesite", "finding-subject"),
            DiagramEntity("rear-tract", "COMMON_TRACT", "Recorded Tract", "finding-tract"),
            DiagramEntity("front-road", "ROAD", "Internal Road", "finding-road"),
        ),
        relationships=(
            DiagramRelationship("rear-relation", "BACKS_TO", "subject-lot", "rear-tract", "finding-tract"),
            DiagramRelationship("front-relation", "FRONTS", "subject-lot", "front-road", "finding-road"),
        ),
    )


def test_renderer_produces_deterministic_schematic_svg():
    first = renderer().render(sample_spec())
    second = renderer().render(sample_spec())
    assert first.svg.startswith("<svg")
    assert first.fingerprint == second.fingerprint
    assert len(first.fingerprint) == 64


def test_renderer_preserves_relative_relationship_zones_without_compass_claims():
    render = renderer().render(sample_spec())
    zones = {placement.relationship_type: placement.zone for placement in render.placements}
    assert zones["BACKS_TO"] == "REAR"
    assert zones["FRONTS"] == "FRONT"
    assert "north" not in render.svg.lower()
    assert "south" not in render.svg.lower()


def test_renderer_always_marks_schematic_as_not_map_and_not_to_scale():
    render = renderer().render(sample_spec())
    assert "not a map and not to scale" in render.notice.lower()
    assert "not a map and not to scale" in render.svg.lower()


def test_renderer_does_not_expose_governed_source_ids_in_svg():
    render = renderer().render(sample_spec())
    assert "finding-subject" not in render.svg
    assert "finding-tract" not in render.svg
    assert "finding-road" not in render.svg


def test_renderer_fails_closed_on_invalid_grammar_spec():
    invalid = DiagramGrammarSpec(
        diagram_id="invalid",
        entities=(DiagramEntity("road", "ROAD", "Road", "finding-road"),),
        relationships=(),
    )
    with pytest.raises(ValueError, match="exactly one SUBJECT_LOT"):
        renderer().render(invalid)
