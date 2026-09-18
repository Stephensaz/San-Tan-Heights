from copy import deepcopy
import json
from pathlib import Path

import pytest
import yaml

from src.presentation.golden_fixtures import GoldenFixtureLoader

ROOT = Path(__file__).resolve().parents[3]
MANIFEST = ROOT / "registries" / "presentation" / "golden-fixture-manifest-v1.0.yaml"
FIXTURES = ROOT / "tests" / "fixtures" / "presentation" / "golden" / "fixtures.json"
EXPECTED = ROOT / "tests" / "fixtures" / "presentation" / "golden" / "expected.json"


def load_set():
    return GoldenFixtureLoader(ROOT).load(MANIFEST)


def test_golden_fixture_set_covers_all_frozen_categories():
    golden = load_set()
    assert len(golden.fixtures) == 16
    assert golden.categories == tuple(
        sorted(
            (
                "NORMAL",
                "SPARSE",
                "DENSE",
                "UNCERTAIN",
                "CONFLICTED",
                "STALE",
                "SPATIAL",
                "MEDIA",
                "ANALYTICAL",
                "HISTORICAL",
                "CHANGE",
                "EMPTY",
                "RESPONSIVE",
                "PAGINATION",
                "PRIVACY_ADVERSARIAL",
                "ACCESSIBILITY",
            )
        )
    )


def test_fixture_identities_are_synthetic_only():
    golden = load_set()
    for fixture in golden.fixtures:
        prop = fixture.payload["property"]
        assert fixture.payload["synthetic_only"] is True
        assert prop["property_id"].startswith("SYNTH-PROP-")
        assert prop["community"] == "San Tan Heights Synthetic"
        assert any(token in prop["address"] for token in ("Example", "Test", "Sample"))


def test_every_fixture_has_independent_agent_seller_public_expectations():
    golden = load_set()
    for fixture in golden.fixtures:
        assert set(("AGENT", "SELLER", "PUBLIC")) <= set(fixture.expected)
        render = fixture.expected["render"]
        assert render["web"] is True
        assert render["pdf"] is True
        assert render["print"] is True


def test_required_edge_cases_are_bound_to_known_fixture_ids():
    golden = load_set()
    coverage = yaml.safe_load(
        (ROOT / "tests" / "fixtures" / "presentation" / "golden" / "coverage-matrix.yaml").read_text()
    )
    ids = {fixture.fixture_id for fixture in golden.fixtures}
    assert set(coverage["required_edge_cases"].values()) <= ids


def test_visual_and_accessibility_expectations_are_present():
    golden = load_set()
    spatial = golden.by_id("SYNTH-SPATIAL-001")
    assert spatial.expected["topology"]["diagram_required"] is True
    assert spatial.expected["accessibility"]["diagram_equivalent_required"] is True

    responsive = golden.by_id("SYNTH-RESPONSIVE-001")
    assert responsive.expected["render"]["required_viewports"] == [
        "desktop_large",
        "desktop",
        "tablet",
        "mobile",
        "mobile_narrow",
    ]

    pagination = golden.by_id("SYNTH-PAGINATION-001")
    assert pagination.expected["pagination"]["multi_page_expected"] is True
    assert pagination.expected["pagination"]["repeated_property_identity_required"] is True


def test_privacy_adversarial_fixture_expects_public_redaction():
    fixture = load_set().by_id("SYNTH-PRIVACY_ADVERSARIAL-001")
    assert "owner_name" in fixture.expected["PUBLIC"]["forbidden_tokens"]
    assert "private_note" in fixture.expected["SELLER"]["forbidden_tokens"]


def test_fixture_fingerprints_are_deterministic():
    first = load_set()
    second = load_set()
    assert first.manifest_fingerprint == second.manifest_fingerprint
    assert first.fixture_set_fingerprint == second.fixture_set_fingerprint
    assert [x.fingerprint for x in first.fixtures] == [x.fingerprint for x in second.fixtures]


def test_truth_and_expected_outcomes_are_separate_artifacts():
    truth = json.loads(FIXTURES.read_text())
    expected = json.loads(EXPECTED.read_text())
    assert "fixtures" in truth and "outcomes" not in truth
    assert "outcomes" in expected and "fixtures" not in expected


def test_privacy_scan_rejects_prohibited_real_data_key(tmp_path):
    manifest = yaml.safe_load(MANIFEST.read_text())
    truth = json.loads(FIXTURES.read_text())
    expected = json.loads(EXPECTED.read_text())

    mutated = deepcopy(truth)
    mutated["fixtures"][0]["property"]["apn"] = "123-45-678"

    truth_path = tmp_path / "fixtures.json"
    expected_path = tmp_path / "expected.json"
    coverage_path = tmp_path / "coverage.yaml"
    schema_path = tmp_path / "schema.json"
    manifest_path = tmp_path / "manifest.yaml"

    truth_path.write_text(json.dumps(mutated))
    expected_path.write_text(json.dumps(expected))
    coverage_path.write_text(
        (ROOT / "tests" / "fixtures" / "presentation" / "golden" / "coverage-matrix.yaml").read_text()
    )
    schema_path.write_text(
        (ROOT / "schemas" / "presentation" / "golden-fixture-v1.0.schema.json").read_text()
    )

    manifest["truth_set"] = str(truth_path.relative_to(tmp_path))
    manifest["expected_set"] = str(expected_path.relative_to(tmp_path))
    manifest["coverage_matrix"] = str(coverage_path.relative_to(tmp_path))
    manifest["schema"] = str(schema_path.relative_to(tmp_path))
    manifest_path.write_text(yaml.safe_dump(manifest, sort_keys=False))

    with pytest.raises(ValueError, match="privacy scan prohibited key"):
        GoldenFixtureLoader(tmp_path).load(manifest_path)


def test_missing_expected_outcome_fails_closed(tmp_path):
    manifest = yaml.safe_load(MANIFEST.read_text())
    truth = json.loads(FIXTURES.read_text())
    expected = json.loads(EXPECTED.read_text())
    expected["outcomes"] = expected["outcomes"][:-1]

    (tmp_path / "fixtures.json").write_text(json.dumps(truth))
    (tmp_path / "expected.json").write_text(json.dumps(expected))
    (tmp_path / "coverage.yaml").write_text(
        (ROOT / "tests" / "fixtures" / "presentation" / "golden" / "coverage-matrix.yaml").read_text()
    )
    (tmp_path / "schema.json").write_text(
        (ROOT / "schemas" / "presentation" / "golden-fixture-v1.0.schema.json").read_text()
    )
    manifest.update(
        {
            "truth_set": "fixtures.json",
            "expected_set": "expected.json",
            "coverage_matrix": "coverage.yaml",
            "schema": "schema.json",
        }
    )
    manifest_path = tmp_path / "manifest.yaml"
    manifest_path.write_text(yaml.safe_dump(manifest, sort_keys=False))

    with pytest.raises(ValueError, match="missing independent expected outcome"):
        GoldenFixtureLoader(tmp_path).load(manifest_path)
