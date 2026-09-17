from pathlib import Path

import pytest

from src.presentation.layout import ResponsiveLayoutPlan
from src.presentation.mobile import MobileNavigationRegistry, MobileNavigationRuntime

ROOT = Path(__file__).resolve().parents[3]
REGISTRY = ROOT / "registries" / "presentation" / "mobile-navigation-v1.0.yaml"


def runtime():
    return MobileNavigationRuntime(MobileNavigationRegistry.load(REGISTRY))


def compact_layout():
    return ResponsiveLayoutPlan(
        mode="COMPACT",
        viewport_width=390,
        card_columns=1,
        media_columns=1,
        gutter_px=16.0,
        content_max_width_px=358.0,
        semantic_order=("header", "summary", "property-dna", "evidence", "freshness"),
    )


def test_mobile_navigation_preserves_canonical_order_and_reachability():
    state = runtime().build(compact_layout(), expanded_ids=("summary",), active_section_id="summary")
    assert [item.section_id for item in state.sections] == list(compact_layout().semantic_order)
    assert all(item.reachable for item in state.sections)
    assert state.sections[1].expanded is True
    assert state.sections[2].expanded is False


def test_collapsed_sections_remain_in_navigation_and_reachable():
    state = runtime().build(compact_layout())
    assert len(state.sections) == len(compact_layout().semantic_order)
    assert all(item.reachable for item in state.sections)
    assert all(item.expanded is False for item in state.sections)


def test_toggle_changes_only_disclosure_state_not_order_or_reachability():
    state = runtime().build(compact_layout())
    toggled = runtime().toggle(state, "evidence")
    assert [item.section_id for item in toggled.sections] == [item.section_id for item in state.sections]
    assert all(item.reachable for item in toggled.sections)
    assert next(item for item in toggled.sections if item.section_id == "evidence").expanded is True


def test_activation_does_not_force_reordering_or_expansion():
    state = runtime().build(compact_layout())
    active = runtime().activate(state, "freshness")
    assert active.active_section_id == "freshness"
    assert [item.section_id for item in active.sections] == list(compact_layout().semantic_order)
    assert all(item.expanded is False for item in active.sections)


def test_mobile_navigation_requires_compact_layout():
    noncompact = ResponsiveLayoutPlan(
        mode="STANDARD",
        viewport_width=900,
        card_columns=2,
        media_columns=2,
        gutter_px=24.0,
        content_max_width_px=852.0,
        semantic_order=("summary", "evidence"),
    )
    with pytest.raises(ValueError, match="requires a COMPACT"):
        runtime().build(noncompact)


def test_mobile_navigation_rejects_unknown_state_targets():
    r = runtime()
    with pytest.raises(ValueError, match="expanded mobile section"):
        r.build(compact_layout(), expanded_ids=("missing",))
    state = r.build(compact_layout())
    with pytest.raises(ValueError, match="unknown mobile section"):
        r.toggle(state, "missing")


def test_mobile_navigation_fingerprint_is_deterministic():
    first = runtime().build(compact_layout(), expanded_ids=("summary",))
    second = runtime().build(compact_layout(), expanded_ids=("summary",))
    assert first.fingerprint == second.fingerprint
    assert len(first.fingerprint) == 64
