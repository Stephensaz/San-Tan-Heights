from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from types import MappingProxyType
from typing import Mapping

import yaml

from src.presentation.golden_fixtures import GoldenFixtureSet
from src.presentation.visual_regression import VisualRegressionRegistry
from src.shared.canonical_json import canonical_json


@dataclass(frozen=True)
class VisualBaselineManifest:
    manifest_id: str
    version: str
    status: str
    source_fixture_set_fingerprint: str
    visual_runtime_fingerprint: str
    fixture_ids: tuple[str, ...]
    targets: Mapping[str, tuple[str, ...]]
    required_structural_assertions: tuple[str, ...]
    fingerprint: str

    @classmethod
    def load(
        cls,
        path: str | Path,
        *,
        fixture_set: GoldenFixtureSet,
        visual_registry: VisualRegressionRegistry,
    ) -> "VisualBaselineManifest":
        raw = yaml.safe_load(Path(path).read_text())
        if raw.get("visual_baseline_manifest_id") != "STH-M8-032-VISUAL-BASELINES-v1.0":
            raise ValueError("unexpected visual baseline manifest id")
        if str(raw.get("version")) != "1.0.0" or raw.get("status") != "LOCKED":
            raise ValueError("visual baseline manifest must be locked v1.0.0")
        if raw.get("source_fixture_set_fingerprint") != fixture_set.fixture_set_fingerprint:
            raise ValueError("visual baseline fixture-set fingerprint mismatch")
        if raw.get("visual_runtime_fingerprint") != visual_registry.fingerprint:
            raise ValueError("visual baseline runtime fingerprint mismatch")

        fixture_ids = tuple(raw.get("fixture_ids") or ())
        expected_ids = tuple(sorted(item.fixture_id for item in fixture_set.fixtures))
        if tuple(sorted(fixture_ids)) != expected_ids or len(set(fixture_ids)) != len(fixture_ids):
            raise ValueError("visual baseline fixture membership mismatch")

        targets_raw = raw.get("targets") or {}
        targets = {
            str(name): tuple((spec or {}).get("viewports") or ())
            for name, spec in targets_raw.items()
        }
        if set(targets) != set(visual_registry.targets):
            raise ValueError("visual baseline target coverage mismatch")
        known_viewports = set(visual_registry.viewports)
        if any(not viewports for viewports in targets.values()):
            raise ValueError("visual baseline target viewports cannot be empty")
        if any(set(viewports) - known_viewports for viewports in targets.values()):
            raise ValueError("visual baseline contains unknown viewport")

        assertions = tuple(raw.get("required_structural_assertions") or ())
        if set(assertions) != set(visual_registry.required_structural_assertions):
            raise ValueError("visual baseline structural assertions mismatch")

        rules = raw.get("baseline_rules") or {}
        required_true = (
            "deterministic_fixture_manifest_only",
            "live_data_prohibited",
            "source_fixture_membership_must_match",
            "visual_runtime_must_match",
            "all_required_targets_must_be_present",
            "all_required_viewports_must_be_present",
            "unresolved_visual_diff_count_must_be_zero",
            "structural_hard_failures_must_be_zero",
        )
        if any(rules.get(key) is not True for key in required_true):
            raise ValueError("visual baseline rules must be fail-closed")

        payload = {
            "visual_baseline_manifest_id": raw["visual_baseline_manifest_id"],
            "version": str(raw["version"]),
            "status": raw["status"],
            "source_fixture_set_fingerprint": raw["source_fixture_set_fingerprint"],
            "visual_runtime_fingerprint": raw["visual_runtime_fingerprint"],
            "fixture_ids": list(fixture_ids),
            "targets": {k: list(v) for k, v in sorted(targets.items())},
            "required_structural_assertions": list(assertions),
            "baseline_rules": rules,
        }
        return cls(
            manifest_id=raw["visual_baseline_manifest_id"],
            version=str(raw["version"]),
            status=raw["status"],
            source_fixture_set_fingerprint=raw["source_fixture_set_fingerprint"],
            visual_runtime_fingerprint=raw["visual_runtime_fingerprint"],
            fixture_ids=fixture_ids,
            targets=MappingProxyType(targets),
            required_structural_assertions=assertions,
            fingerprint=sha256(canonical_json(payload).encode("utf-8")).hexdigest(),
        )
