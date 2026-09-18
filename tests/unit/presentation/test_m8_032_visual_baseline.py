from pathlib import Path

import pytest
import yaml

from src.presentation.golden_fixtures import GoldenFixtureLoader, VisualBaselineManifest
from src.presentation.visual_regression import VisualRegressionRegistry

ROOT = Path(__file__).resolve().parents[3]
FIXTURES = ROOT / "registries" / "presentation" / "golden-fixture-manifest-v1.0.yaml"
VISUAL = ROOT / "registries" / "presentation" / "visual-regression-v1.0.yaml"
BASELINE = ROOT / "tests" / "visual" / "baselines" / "m8-032" / "manifest.yaml"


def load():
    fixture_set = GoldenFixtureLoader(ROOT).load(FIXTURES)
    visual = VisualRegressionRegistry.load(VISUAL)
    return VisualBaselineManifest.load(BASELINE, fixture_set=fixture_set, visual_registry=visual)


def test_visual_baseline_manifest_is_locked_and_bound_to_frozen_fixture_set():
    baseline = load()
    assert baseline.status == "LOCKED"
    assert len(baseline.fixture_ids) == 16
    assert len(baseline.fingerprint) == 64


def test_visual_baseline_covers_every_locked_target_and_required_viewport_set():
    baseline = load()
    assert set(baseline.targets) == {"PUBLIC_WEB", "SELLER_WEB", "AGENT_WEB", "PDF", "PRINT"}
    assert baseline.targets["PUBLIC_WEB"] == ("desktop_large", "desktop", "tablet", "mobile", "mobile_narrow")
    assert baseline.targets["SELLER_WEB"] == ("desktop", "tablet", "mobile")
    assert baseline.targets["AGENT_WEB"] == ("desktop_large", "desktop")
    assert baseline.targets["PDF"] == ("desktop",)
    assert baseline.targets["PRINT"] == ("desktop",)


def test_visual_baseline_contains_all_structural_assertions():
    baseline = load()
    visual = VisualRegressionRegistry.load(VISUAL)
    assert set(baseline.required_structural_assertions) == set(visual.required_structural_assertions)


def test_visual_baseline_fails_closed_on_fixture_fingerprint_drift(tmp_path):
    raw = yaml.safe_load(BASELINE.read_text())
    raw["source_fixture_set_fingerprint"] = "0" * 64
    path = tmp_path / "manifest.yaml"
    path.write_text(yaml.safe_dump(raw, sort_keys=False))
    fixture_set = GoldenFixtureLoader(ROOT).load(FIXTURES)
    visual = VisualRegressionRegistry.load(VISUAL)
    with pytest.raises(ValueError, match="fixture-set fingerprint mismatch"):
        VisualBaselineManifest.load(path, fixture_set=fixture_set, visual_registry=visual)


def test_visual_baseline_fails_closed_on_runtime_drift(tmp_path):
    raw = yaml.safe_load(BASELINE.read_text())
    raw["visual_runtime_fingerprint"] = "0" * 64
    path = tmp_path / "manifest.yaml"
    path.write_text(yaml.safe_dump(raw, sort_keys=False))
    fixture_set = GoldenFixtureLoader(ROOT).load(FIXTURES)
    visual = VisualRegressionRegistry.load(VISUAL)
    with pytest.raises(ValueError, match="runtime fingerprint mismatch"):
        VisualBaselineManifest.load(path, fixture_set=fixture_set, visual_registry=visual)
