from pathlib import Path

import pytest

from src.presentation.tokens import DesignTokenRegistry

ROOT = Path(__file__).resolve().parents[3]
REGISTRY = ROOT / "registries" / "presentation" / "design-tokens-v1.0.yaml"


def test_design_token_registry_loads_locked_semantic_tokens():
    registry = DesignTokenRegistry.load(REGISTRY)
    assert registry.registry_id == "STH-DESIGN-TOKENS-v1.0"
    assert registry.version == "1.0.0"
    assert registry.status == "LOCKED"
    assert registry.colors["surface_primary"] == "#FFFFFF"
    assert registry.colors["accent_primary"] == "#D3BC8D"
    assert registry.spacing["md"] == 16.0
    assert len(registry.fingerprint) == 64


def test_design_token_registry_is_read_only():
    registry = DesignTokenRegistry.load(REGISTRY)
    with pytest.raises(TypeError):
        registry.colors["surface_primary"] = "#000000"


def test_design_token_fingerprint_is_deterministic():
    first = DesignTokenRegistry.load(REGISTRY)
    second = DesignTokenRegistry.load(REGISTRY)
    assert first.fingerprint == second.fingerprint


def test_design_tokens_do_not_define_audience_or_brand_runtime_policy():
    registry = DesignTokenRegistry.load(REGISTRY)
    assert "agent" not in registry.colors
    assert "seller" not in registry.colors
    assert "public" not in registry.colors
    assert "logo" not in registry.colors
