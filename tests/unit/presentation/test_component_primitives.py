import pytest

from src.presentation.components import card, disclosure, divider, stack, text


def test_component_primitives_are_deterministic_and_immutable():
    heading = text("property-heading", "Property Intelligence")
    body = text("property-body", "Verified information only.")
    root = card("property-card", stack("property-stack", heading, divider("property-divider"), body))
    assert root.fingerprint == card("property-card", stack("property-stack", heading, divider("property-divider"), body)).fingerprint
    with pytest.raises(TypeError):
        root.props["surface_token"] = "surface_subtle"


def test_disclosure_requires_label_and_content():
    child = text("evidence-text", "Evidence details")
    assert disclosure("evidence-disclosure", "Evidence", child).children == (child,)
    with pytest.raises(ValueError):
        disclosure("empty-disclosure", "", child)


def test_semantic_override_properties_are_rejected():
    from src.presentation.components.primitives import ComponentPrimitive, PrimitiveKind
    with pytest.raises(ValueError):
        ComponentPrimitive("bad-card", PrimitiveKind.CARD, {"score": 95})


def test_text_requires_approved_nonempty_text():
    with pytest.raises(ValueError):
        text("empty-text", "   ")
