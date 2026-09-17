from pathlib import Path

import pytest

from src.presentation.branding import BrandingRegistry, BrandingRuntime, DesignTokenSet
from src.presentation.package import PresentationAudience, PresentationChannel

ROOT = Path(__file__).resolve().parents[3]
BRANDING_REGISTRY = ROOT / "registries" / "presentation" / "branding-v1.0.yaml"
DESIGN_TOKENS = ROOT / "registries" / "presentation" / "design-tokens-v1.0.yaml"


def runtime():
    return BrandingRuntime(
        BrandingRegistry.load(BRANDING_REGISTRY),
        DesignTokenSet.load(DESIGN_TOKENS),
    )


def test_branding_registry_is_locked_and_nonsemantic():
    registry = BrandingRegistry.load(BRANDING_REGISTRY)
    assert registry.status == "LOCKED"
    assert registry.display_name == "San Tan Heights"
    assert registry.descriptor == "Property Intelligence"
    assert registry.rules["branding_does_not_change_property_facts"] is True
    assert registry.rules["branding_does_not_change_audience_eligibility"] is True
    assert registry.rules["branding_does_not_hide_required_disclosures"] is True
    assert registry.rules["allow_runtime_color_override"] is False
    assert registry.rules["allow_runtime_typography_override"] is False


def test_branding_runtime_uses_existing_locked_design_tokens():
    plan = runtime().plan(PresentationAudience.PUBLIC, PresentationChannel.WEB)
    assert plan.colors["surface_primary"] == "#FFFFFF"
    assert plan.colors["text_primary"] == "#000000"
    assert plan.colors["border_default"] == "#A5ACAF"
    assert plan.colors["accent_primary"] == "#D3BC8D"
    assert plan.layout["content_max_width"] == 1200


def test_brand_identity_and_tokens_remain_same_across_audiences_and_channels():
    agent = runtime().plan(PresentationAudience.AGENT, PresentationChannel.PDF)
    public = runtime().plan(PresentationAudience.PUBLIC, PresentationChannel.WEB)
    assert agent.brand_id == public.brand_id
    assert agent.design_token_fingerprint == public.design_token_fingerprint
    assert dict(agent.colors) == dict(public.colors)
    assert agent.audience != public.audience
    assert agent.channel != public.channel


def test_branding_plan_is_deterministic():
    first = runtime().plan(PresentationAudience.SELLER, PresentationChannel.PRINT)
    second = runtime().plan(PresentationAudience.SELLER, PresentationChannel.PRINT)
    assert first.fingerprint == second.fingerprint
    assert len(first.fingerprint) == 64


def test_branding_runtime_rejects_invalid_audience_or_channel():
    with pytest.raises(ValueError, match="PresentationAudience"):
        runtime().plan("PUBLIC", PresentationChannel.WEB)
    with pytest.raises(ValueError, match="PresentationChannel"):
        runtime().plan(PresentationAudience.PUBLIC, "WEB")
