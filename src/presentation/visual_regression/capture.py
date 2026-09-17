from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from types import MappingProxyType
from typing import Mapping

import yaml

from src.shared.canonical_json import canonical_json

_EXPECTED_ID = "STH-VISUAL-REGRESSION-v1.0"
_EXPECTED_VERSION = "1.0.0"
_EXPECTED_STATUS = "LOCKED"


@dataclass(frozen=True)
class VisualRegressionRegistry:
    registry_id: str
    version: str
    status: str
    runtime: Mapping[str, object]
    viewports: Mapping[str, tuple[int, int]]
    targets: tuple[str, ...]
    required_structural_assertions: tuple[str, ...]
    hard_failure_codes: frozenset[str]
    diff_classes: tuple[str, ...]
    fingerprint: str

    @classmethod
    def load(cls, path: str | Path) -> "VisualRegressionRegistry":
        raw = yaml.safe_load(Path(path).read_text())
        if raw.get("visual_regression_id") != _EXPECTED_ID:
            raise ValueError("unexpected visual regression id")
        if str(raw.get("version")) != _EXPECTED_VERSION:
            raise ValueError("unexpected visual regression version")
        if raw.get("status") != _EXPECTED_STATUS:
            raise ValueError("visual regression registry must be LOCKED")
        runtime = dict(raw.get("runtime") or {})
        if runtime.get("animations_enabled") is not False:
            raise ValueError("animations must be disabled")
        viewports = {k: tuple(v) for k, v in (raw.get("viewports") or {}).items()}
        payload = {
            "visual_regression_id": _EXPECTED_ID,
            "version": _EXPECTED_VERSION,
            "status": _EXPECTED_STATUS,
            "runtime": runtime,
            "viewports": {k: list(v) for k, v in viewports.items()},
            "targets": raw.get("targets") or [],
            "required_structural_assertions": raw.get("required_structural_assertions") or [],
            "hard_failure_codes": raw.get("hard_failure_codes") or [],
            "diff_classes": raw.get("diff_classes") or [],
        }
        return cls(
            registry_id=_EXPECTED_ID,
            version=_EXPECTED_VERSION,
            status=_EXPECTED_STATUS,
            runtime=MappingProxyType(runtime),
            viewports=MappingProxyType(viewports),
            targets=tuple(payload["targets"]),
            required_structural_assertions=tuple(payload["required_structural_assertions"]),
            hard_failure_codes=frozenset(payload["hard_failure_codes"]),
            diff_classes=tuple(payload["diff_classes"]),
            fingerprint=sha256(canonical_json(payload).encode("utf-8")).hexdigest(),
        )


@dataclass(frozen=True)
class StructuralAssertion:
    code: str
    passed: bool
    location: str

    def canonical_payload(self) -> dict[str, object]:
        return {"code": self.code, "passed": self.passed, "location": self.location}


@dataclass(frozen=True)
class VisualCapture:
    fixture_id: str
    target: str
    viewport: str
    image_hash: str
    runtime_fingerprint: str
    assertions: tuple[StructuralAssertion, ...]

    def canonical_payload(self) -> dict[str, object]:
        return {
            "fixture_id": self.fixture_id,
            "target": self.target,
            "viewport": self.viewport,
            "image_hash": self.image_hash,
            "runtime_fingerprint": self.runtime_fingerprint,
            "assertions": [a.canonical_payload() for a in self.assertions],
        }

    @property
    def fingerprint(self) -> str:
        return sha256(canonical_json(self.canonical_payload()).encode("utf-8")).hexdigest()


class VisualCaptureHarness:
    def __init__(self, registry: VisualRegressionRegistry) -> None:
        self.registry = registry

    def capture(self, *, fixture_id: str, target: str, viewport: str, png_bytes: bytes, assertions: tuple[StructuralAssertion, ...]) -> VisualCapture:
        if target not in self.registry.targets:
            raise ValueError("unsupported visual target")
        if viewport not in self.registry.viewports:
            raise ValueError("unsupported viewport")
        if not fixture_id.strip():
            raise ValueError("fixture_id is required")
        required = set(self.registry.required_structural_assertions)
        seen = {a.code for a in assertions}
        missing = required - seen
        if missing:
            raise ValueError(f"missing structural assertions: {sorted(missing)}")
        return VisualCapture(
            fixture_id=fixture_id,
            target=target,
            viewport=viewport,
            image_hash=sha256(png_bytes).hexdigest(),
            runtime_fingerprint=self.registry.fingerprint,
            assertions=tuple(sorted(assertions, key=lambda a: (a.code, a.location))),
        )
