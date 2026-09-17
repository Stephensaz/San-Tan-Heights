from pathlib import Path

import pytest

from src.presentation.visual_regression import (
    StructuralAssertion,
    VisualCaptureHarness,
    VisualComparator,
    VisualDiffClass,
    VisualDiffClassifier,
    VisualRegressionRegistry,
)

ROOT = Path(__file__).resolve().parents[3]
REGISTRY = ROOT / "registries" / "presentation" / "visual-regression-v1.0.yaml"


def registry():
    return VisualRegressionRegistry.load(REGISTRY)


def assertions(*, failed=()):
    required = registry().required_structural_assertions
    items = [
        StructuralAssertion(code, code not in failed, f"fixture/{code.lower()}")
        for code in required
    ]
    items.extend(
        StructuralAssertion(code, False, f"fixture/{code.lower()}")
        for code in failed
        if code not in required
    )
    return tuple(items)


def capture(*, image=b"same", failed=(), target="PUBLIC_WEB", viewport="mobile"):
    return VisualCaptureHarness(registry()).capture(
        fixture_id="fixture-1",
        target=target,
        viewport=viewport,
        png_bytes=image,
        assertions=assertions(failed=failed),
    )


def test_registry_locks_runtime_and_viewports():
    r = registry()
    assert r.status == "LOCKED"
    assert r.runtime["browser"] == "chromium"
    assert r.runtime["os"] == "ubuntu-24.04"
    assert r.runtime["timezone"] == "America/Phoenix"
    assert r.runtime["animations_enabled"] is False
    assert r.viewports["desktop_large"] == (1440, 1000)
    assert r.viewports["mobile_narrow"] == (320, 800)


def test_capture_requires_all_structural_assertions():
    r = registry()
    with pytest.raises(ValueError, match="missing structural assertions"):
        VisualCaptureHarness(r).capture(
            fixture_id="fixture-1",
            target="PUBLIC_WEB",
            viewport="mobile",
            png_bytes=b"png",
            assertions=(),
        )


def test_capture_is_deterministic():
    first = capture()
    second = capture()
    assert first.fingerprint == second.fingerprint
    assert first.image_hash == second.image_hash


def test_comparator_rejects_cross_target_or_viewport_comparison():
    comparator = VisualComparator(registry())
    with pytest.raises(ValueError, match="target/viewport mismatch"):
        comparator.compare(capture(), capture(target="SELLER_WEB"), pixel_difference_ratio=0, perceptual_difference=0)


def test_no_difference_classifies_expected():
    r = registry()
    comparison = VisualComparator(r).compare(
        capture(),
        capture(),
        pixel_difference_ratio=0.0,
        perceptual_difference=0.0,
    )
    decision = VisualDiffClassifier(r).classify(comparison, expected_change=False)
    assert decision.classification is VisualDiffClass.EXPECTED


def test_small_unapproved_difference_requires_review():
    r = registry()
    comparison = VisualComparator(r).compare(
        capture(),
        capture(image=b"different"),
        pixel_difference_ratio=0.005,
        perceptual_difference=0.005,
    )
    decision = VisualDiffClassifier(r).classify(comparison, expected_change=False)
    assert decision.classification is VisualDiffClass.REVIEW_REQUIRED


def test_large_unapproved_difference_is_unexpected():
    r = registry()
    comparison = VisualComparator(r).compare(
        capture(),
        capture(image=b"different"),
        pixel_difference_ratio=0.02,
        perceptual_difference=0.02,
    )
    decision = VisualDiffClassifier(r).classify(comparison, expected_change=False)
    assert decision.classification is VisualDiffClass.UNEXPECTED


def test_expected_change_must_produce_measurable_difference():
    r = registry()
    comparison = VisualComparator(r).compare(
        capture(),
        capture(),
        pixel_difference_ratio=0.0,
        perceptual_difference=0.0,
    )
    decision = VisualDiffClassifier(r).classify(comparison, expected_change=True)
    assert decision.classification is VisualDiffClass.REVIEW_REQUIRED


def test_hard_failure_overrides_expected_change():
    r = registry()
    comparison = VisualComparator(r).compare(
        capture(),
        capture(image=b"different", failed=("CROPPED_TEXT",)),
        pixel_difference_ratio=0.02,
        perceptual_difference=0.02,
    )
    decision = VisualDiffClassifier(r).classify(comparison, expected_change=True)
    assert decision.classification is VisualDiffClass.UNEXPECTED
    assert "CROPPED_TEXT" in decision.reason
