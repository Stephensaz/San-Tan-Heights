from pathlib import Path

import pytest

from src.presentation.labels import FriendlyLabelRuntime
from src.presentation.package import PresentationAudience

ROOT = Path(__file__).resolve().parents[3]


def test_runtime_uses_existing_friendly_label_registry():
    runtime = FriendlyLabelRuntime.from_repository(ROOT)
    assert runtime.resolve("CANONICAL_PHASE", PresentationAudience.AGENT).label == "Canonical Phase"
    assert runtime.resolve("CANONICAL_PHASE", PresentationAudience.SELLER).label == "Community Phase"
    assert runtime.resolve("CANONICAL_PHASE", PresentationAudience.PUBLIC).label == "Community Phase"


def test_runtime_resolves_multiple_terms_without_reordering():
    runtime = FriendlyLabelRuntime.from_repository(ROOT)
    results = runtime.resolve_many(("BUILDER_IDENTITY", "LOT_IDENTITY"), PresentationAudience.SELLER)
    assert [item.term_id for item in results] == ["BUILDER_IDENTITY", "LOT_IDENTITY"]
    assert [item.label for item in results] == ["Builder", "Homesite"]


def test_runtime_fails_closed_for_unknown_term():
    runtime = FriendlyLabelRuntime.from_repository(ROOT)
    with pytest.raises(ValueError):
        runtime.resolve("UNKNOWN_TERM", PresentationAudience.PUBLIC)


def test_runtime_does_not_fallback_between_audiences():
    runtime = FriendlyLabelRuntime.from_repository(ROOT)
    result = runtime.resolve("REAR_ADJACENCY", PresentationAudience.PUBLIC)
    assert result.label == "Rear Property Relationship"
    assert result.audience is PresentationAudience.PUBLIC
