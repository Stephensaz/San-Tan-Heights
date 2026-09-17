from pathlib import Path

import pytest

from src.presentation.layout import ResponsiveLayoutRegistry, ResponsiveLayoutRuntime
from src.presentation.tokens import DesignTokenRegistry

ROOT = Path(__file__).resolve().parents[3]
LAYOUT = ROOT / "registries" / "presentation" / "responsive-layout-v1.0.yaml"
TOKENS = ROOT / "registries" / "presentation" / "design-tokens-v1.0.yaml"


def runtime():
    return ResponsiveLayoutRuntime(
        ResponsiveLayoutRegistry.load(LAYOUT),
        DesignTokenRegistry.load(TOKENS),
    )


def test_responsive_modes_resolve_at_locked_breakpoints():
    r = runtime()
    assert r.plan(viewport_width=390, semantic_order=("summary",)).mode == "COMPACT"
    assert r.plan(viewport_width=900, semantic_order=("summary",)).mode == "STANDARD"
    assert r.plan(viewport_width=1440, semantic_order=("summary",)).mode == "WIDE"


def test_responsive_layout_preserves_semantic_order_across_viewports():
    order = ("header", "summary", "property-dna", "evidence", "freshness")
    r = runtime()
    plans = [r.plan(viewport_width=width, semantic_order=order) for width in (390, 900, 1440)]
    assert all(plan.semantic_order == order for plan in plans)


def test_responsive_layout_changes_columns_without_hiding_content():
    order = ("card-a", "card-b", "card-c")
    r = runtime()
    compact = r.plan(viewport_width=390, semantic_order=order)
    wide = r.plan(viewport_width=1440, semantic_order=order)
    assert compact.card_columns == 1
    assert wide.card_columns == 2
    assert compact.semantic_order == wide.semantic_order == order


def test_responsive_layout_uses_locked_design_token_gutters_and_max_width():
    r = runtime()
    compact = r.plan(viewport_width=390, semantic_order=("summary",))
    wide = r.plan(viewport_width=1440, semantic_order=("summary",))
    assert compact.gutter_px == 16.0
    assert compact.content_max_width_px == 358.0
    assert wide.gutter_px == 32.0
    assert wide.content_max_width_px == 1200.0


def test_responsive_layout_rejects_uncertified_viewport_or_invalid_order():
    r = runtime()
    with pytest.raises(ValueError, match="outside the certified responsive range"):
        r.plan(viewport_width=300, semantic_order=("summary",))
    with pytest.raises(ValueError, match="must be unique"):
        r.plan(viewport_width=390, semantic_order=("summary", "summary"))


def test_responsive_layout_fingerprint_is_deterministic():
    r = runtime()
    first = r.plan(viewport_width=900, semantic_order=("summary", "evidence"))
    second = r.plan(viewport_width=900, semantic_order=("summary", "evidence"))
    assert first.fingerprint == second.fingerprint
    assert len(first.fingerprint) == 64
