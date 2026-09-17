from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256

from src.presentation.visual_regression.capture import VisualCapture, VisualRegressionRegistry
from src.shared.canonical_json import canonical_json


@dataclass(frozen=True)
class VisualComparison:
    baseline_fingerprint: str
    candidate_fingerprint: str
    pixel_difference_ratio: float
    perceptual_difference: float
    failed_assertions: tuple[str, ...]

    def canonical_payload(self) -> dict[str, object]:
        return {
            "baseline_fingerprint": self.baseline_fingerprint,
            "candidate_fingerprint": self.candidate_fingerprint,
            "pixel_difference_ratio": self.pixel_difference_ratio,
            "perceptual_difference": self.perceptual_difference,
            "failed_assertions": list(self.failed_assertions),
        }

    @property
    def fingerprint(self) -> str:
        return sha256(canonical_json(self.canonical_payload()).encode("utf-8")).hexdigest()


class VisualComparator:
    def __init__(self, registry: VisualRegressionRegistry) -> None:
        self.registry = registry

    def compare(
        self,
        baseline: VisualCapture,
        candidate: VisualCapture,
        *,
        pixel_difference_ratio: float,
        perceptual_difference: float,
    ) -> VisualComparison:
        if baseline.fixture_id != candidate.fixture_id:
            raise ValueError("visual fixture mismatch")
        if baseline.target != candidate.target or baseline.viewport != candidate.viewport:
            raise ValueError("visual target/viewport mismatch")
        if baseline.runtime_fingerprint != self.registry.fingerprint or candidate.runtime_fingerprint != self.registry.fingerprint:
            raise ValueError("visual runtime fingerprint mismatch")
        if not 0.0 <= pixel_difference_ratio <= 1.0:
            raise ValueError("pixel_difference_ratio must be between 0 and 1")
        if perceptual_difference < 0.0:
            raise ValueError("perceptual_difference must be nonnegative")

        failed = tuple(sorted(a.code for a in candidate.assertions if not a.passed))
        return VisualComparison(
            baseline_fingerprint=baseline.fingerprint,
            candidate_fingerprint=candidate.fingerprint,
            pixel_difference_ratio=pixel_difference_ratio,
            perceptual_difference=perceptual_difference,
            failed_assertions=failed,
        )
