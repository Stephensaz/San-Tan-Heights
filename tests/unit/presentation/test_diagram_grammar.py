from pathlib import Path

import pytest

from src.presentation.diagram import (
    DiagramEntity,
    DiagramGrammarRegistry,
    DiagramGrammarRuntime,
    DiagramGrammarSpec,
    DiagramRelationship,
)

ROOT = Path(__file__).resolve().parents[3]
REGISTRY_PATH = ROOT / "registries" / "presentation" / "diagram-grammar-v1.0.yaml"


def valid_spec():
    return DiagramGrammarSpec(
        diagram_id="lot-context",
        entities=(
            DiagramEntity("subject-lot", "SUBJECT_LOT", "Subject Homesite", "finding-subject"),
            DiagramEntity("rear-tract", "COMMON_TRACT", "Recorded Tract", "finding-tract"),
        ),
        relationships=(
            DiagramRelationship("rear-relation", "BACKS_TO", "subject-lot", "rear-tract", "finding-tract"),
        ),
    )


def test_diagram_grammar_registry_loads_locked_schematic_contract():
    registry = DiagramGrammarRegistry.load(REGISTRY_PATH)
    assert registry.grammar_id == "STH-DIAGRAM-GRAMMAR-v1.0"
    assert registry.diagram_kind == "SCHEMATIC_RELATIONSHIP"
    assert registry.rules["allow_coordinates"] is False
    assert registry.rules["allow_distances"] is False
    assert registry.rules["allow_value_claims"] is False
    assert len(registry.fingerprint) == 64


def test_runtime_accepts_governed_relationship_spec_and_fingerprint_is_deterministic():
    runtime = DiagramGrammarRuntime(DiagramGrammarRegistry.load(REGISTRY_PATH))
    first = runtime.validate(valid_spec())
    second = runtime.validate(valid_spec())
    assert first.fingerprint == second.fingerprint


def test_runtime_requires_exactly_one_subject_lot():
    runtime = DiagramGrammarRuntime(DiagramGrammarRegistry.load(REGISTRY_PATH))
    spec = DiagramGrammarSpec(
        diagram_id="invalid-subject",
        entities=(DiagramEntity("road", "ROAD", "Road", "finding-road"),),
        relationships=(),
    )
    with pytest.raises(ValueError, match="exactly one SUBJECT_LOT"):
        runtime.validate(spec)


def test_runtime_rejects_unknown_relationship_entity_reference():
    runtime = DiagramGrammarRuntime(DiagramGrammarRegistry.load(REGISTRY_PATH))
    spec = DiagramGrammarSpec(
        diagram_id="dangling-reference",
        entities=(DiagramEntity("subject-lot", "SUBJECT_LOT", None, "finding-subject"),),
        relationships=(
            DiagramRelationship("rear-relation", "BACKS_TO", "subject-lot", "missing-tract", "finding-tract"),
        ),
    )
    with pytest.raises(ValueError, match="unknown entity"):
        runtime.validate(spec)


def test_runtime_rejects_unsupported_entity_type():
    runtime = DiagramGrammarRuntime(DiagramGrammarRegistry.load(REGISTRY_PATH))
    spec = DiagramGrammarSpec(
        diagram_id="unsupported-entity",
        entities=(DiagramEntity("subject-lot", "PROPERTY_VALUE", None, "finding-subject"),),
        relationships=(),
    )
    with pytest.raises(ValueError, match="unsupported diagram entity type"):
        runtime.validate(spec)


def test_canonical_grammar_payload_has_no_coordinate_distance_or_value_fields():
    payload = valid_spec().canonical_payload()
    text = str(payload).lower()
    for prohibited in ("latitude", "longitude", "coordinate", "distance", "price", "premium", "value"):
        assert prohibited not in text
