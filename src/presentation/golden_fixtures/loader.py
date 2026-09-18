from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping

import jsonschema
import yaml

from src.shared.canonical_json import canonical_json

_EXPECTED_MANIFEST_ID = "STH-M8-032-GOLDEN-MANIFEST-v1.0"
_EXPECTED_VERSION = "1.0.0"
_EXPECTED_STATUS = "LOCKED"


@dataclass(frozen=True)
class GoldenFixture:
    fixture_id: str
    category: str
    payload: Mapping[str, Any]
    expected: Mapping[str, Any]
    fingerprint: str


@dataclass(frozen=True)
class GoldenFixtureSet:
    manifest_id: str
    version: str
    manifest_fingerprint: str
    fixture_set_fingerprint: str
    fixtures: tuple[GoldenFixture, ...]
    categories: tuple[str, ...]

    def by_id(self, fixture_id: str) -> GoldenFixture:
        for fixture in self.fixtures:
            if fixture.fixture_id == fixture_id:
                return fixture
        raise KeyError(fixture_id)


class GoldenFixtureLoader:
    """Load and certify the M8-032 synthetic-only golden presentation fixture set."""

    def __init__(self, repository_root: str | Path) -> None:
        self.root = Path(repository_root)

    def load(self, manifest_path: str | Path) -> GoldenFixtureSet:
        manifest_path = Path(manifest_path)
        manifest = yaml.safe_load(manifest_path.read_text())
        self._validate_manifest(manifest)

        schema = json.loads((self.root / manifest["schema"]).read_text())
        truth = json.loads((self.root / manifest["truth_set"]).read_text())
        expected = json.loads((self.root / manifest["expected_set"]).read_text())
        coverage = yaml.safe_load((self.root / manifest["coverage_matrix"]).read_text())

        fixtures = truth.get("fixtures")
        outcomes = expected.get("outcomes")
        if not isinstance(fixtures, list) or not fixtures:
            raise ValueError("golden truth set must contain fixtures")
        if not isinstance(outcomes, list) or not outcomes:
            raise ValueError("golden expected set must contain outcomes")

        by_expected = {item.get("fixture_id"): item.get("expected") for item in outcomes}
        if None in by_expected or len(by_expected) != len(outcomes):
            raise ValueError("expected fixture ids must be unique and nonblank")

        required_categories = tuple(coverage.get("required_categories") or ())
        required_audiences = tuple(coverage.get("required_audiences") or ())
        required_surfaces = tuple(coverage.get("required_surfaces") or ())
        if required_audiences != ("AGENT", "SELLER", "PUBLIC"):
            raise ValueError("golden fixtures must cover Agent, Seller, and Public")
        if required_surfaces != ("WEB", "PDF", "PRINT"):
            raise ValueError("golden fixtures must cover web, PDF, and print")

        seen_ids: set[str] = set()
        seen_categories: set[str] = set()
        records: list[GoldenFixture] = []
        for payload in fixtures:
            jsonschema.validate(payload, schema)
            fixture_id = str(payload["fixture_id"])
            category = str(payload["category"])
            if fixture_id in seen_ids:
                raise ValueError(f"duplicate golden fixture id: {fixture_id}")
            seen_ids.add(fixture_id)
            seen_categories.add(category)

            if fixture_id not in by_expected:
                raise ValueError(f"missing independent expected outcome: {fixture_id}")
            outcome = by_expected[fixture_id]
            if not isinstance(outcome, dict):
                raise ValueError(f"expected outcome must be an object: {fixture_id}")
            if set(("AGENT", "SELLER", "PUBLIC")) - set(outcome):
                raise ValueError(f"missing audience expectation: {fixture_id}")
            render = outcome.get("render") or {}
            if not all(render.get(key) is True for key in ("web", "pdf", "print")):
                raise ValueError(f"fixture must define web/pdf/print expectations: {fixture_id}")

            self._privacy_scan(payload, manifest)
            self._privacy_scan(outcome, manifest)
            self._require_synthetic_identity(payload)

            fingerprint = sha256(
                canonical_json({"truth": payload, "expected": outcome}).encode("utf-8")
            ).hexdigest()
            records.append(
                GoldenFixture(
                    fixture_id=fixture_id,
                    category=category,
                    payload=MappingProxyType(payload),
                    expected=MappingProxyType(outcome),
                    fingerprint=fingerprint,
                )
            )

        if set(by_expected) != seen_ids:
            extras = sorted(set(by_expected) - seen_ids)
            raise ValueError(f"expected outcomes without truth fixtures: {extras}")
        if set(required_categories) != seen_categories:
            missing = sorted(set(required_categories) - seen_categories)
            extra = sorted(seen_categories - set(required_categories))
            raise ValueError(f"golden category coverage mismatch: missing={missing}, extra={extra}")

        edge_cases = coverage.get("required_edge_cases") or {}
        for name, fixture_id in edge_cases.items():
            if fixture_id not in seen_ids:
                raise ValueError(f"coverage matrix references unknown fixture: {name}={fixture_id}")

        ordered = tuple(sorted(records, key=lambda item: item.fixture_id))
        manifest_fingerprint = sha256(canonical_json(manifest).encode("utf-8")).hexdigest()
        set_payload = {
            "manifest_fingerprint": manifest_fingerprint,
            "fixture_fingerprints": [
                {"fixture_id": item.fixture_id, "fingerprint": item.fingerprint}
                for item in ordered
            ],
        }
        return GoldenFixtureSet(
            manifest_id=_EXPECTED_MANIFEST_ID,
            version=_EXPECTED_VERSION,
            manifest_fingerprint=manifest_fingerprint,
            fixture_set_fingerprint=sha256(canonical_json(set_payload).encode("utf-8")).hexdigest(),
            fixtures=ordered,
            categories=tuple(sorted(seen_categories)),
        )

    @staticmethod
    def _validate_manifest(manifest: Mapping[str, Any]) -> None:
        if manifest.get("golden_fixture_manifest_id") != _EXPECTED_MANIFEST_ID:
            raise ValueError("unexpected golden fixture manifest id")
        if str(manifest.get("version")) != _EXPECTED_VERSION:
            raise ValueError("unexpected golden fixture manifest version")
        if manifest.get("status") != _EXPECTED_STATUS:
            raise ValueError("golden fixture manifest must be LOCKED")
        if manifest.get("synthetic_only") is not True:
            raise ValueError("golden fixture manifest must be synthetic-only")
        requirements = manifest.get("certification_requirements") or {}
        for key in (
            "require_independent_expected_outcomes",
            "require_all_audiences",
            "require_all_categories",
            "require_all_surfaces",
            "require_deterministic_fingerprints",
            "require_privacy_scan_pass",
            "prohibit_live_data_access",
            "prohibit_real_property_identity",
        ):
            if requirements.get(key) is not True:
                raise ValueError(f"golden fixture certification requirement must be true: {key}")

    @staticmethod
    def _require_synthetic_identity(payload: Mapping[str, Any]) -> None:
        if payload.get("synthetic_only") is not True:
            raise ValueError("golden fixture must be synthetic-only")
        prop = payload.get("property") or {}
        property_id = str(prop.get("property_id") or "")
        address = str(prop.get("address") or "")
        community = str(prop.get("community") or "")
        if not property_id.startswith("SYNTH-PROP-"):
            raise ValueError("golden fixture property id must be synthetic")
        if not any(token in address for token in ("Example", "Test", "Sample")):
            raise ValueError("golden fixture address must use reserved synthetic naming")
        if community != "San Tan Heights Synthetic":
            raise ValueError("golden fixture community must be synthetic")

    @classmethod
    def _privacy_scan(cls, value: Any, manifest: Mapping[str, Any], path: str = "$") -> None:
        rules = manifest.get("privacy_rules") or {}
        prohibited_keys = {str(item).lower() for item in rules.get("prohibited_keys") or ()}
        prohibited_patterns = tuple(str(item).lower() for item in rules.get("prohibited_value_patterns") or ())

        if isinstance(value, dict):
            for key, child in value.items():
                normalized_key = str(key).lower()
                if normalized_key in prohibited_keys:
                    raise ValueError(f"privacy scan prohibited key at {path}.{key}")
                if normalized_key == "forbidden_tokens":
                    if not isinstance(child, list) or any(not isinstance(item, str) for item in child):
                        raise ValueError(f"forbidden_tokens must be a string list at {path}.{key}")
                    continue
                cls._privacy_scan(child, manifest, f"{path}.{key}")
        elif isinstance(value, list):
            for index, child in enumerate(value):
                cls._privacy_scan(child, manifest, f"{path}[{index}]")
        elif isinstance(value, str):
            lowered = value.lower()
            if any(pattern in lowered for pattern in prohibited_patterns):
                raise ValueError(f"privacy scan prohibited value pattern at {path}")
