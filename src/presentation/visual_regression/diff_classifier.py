from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from src.presentation.visual_regression.capture import VisualRegressionRegistry
from src.presentation.visual_regression.compare import VisualComparison


class VisualDiffClass(str, Enum):
    EXPECTED = "EXPECTED"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    UNEXPECTED = "UNEXPECTED"


@dataclass(frozen=True)
class VisualDiffDecision:
    classification: VisualDiffClass
    reason: str


class VisualDiffClassifier:
    def __init__(self, registry: VisualRegressionRegistry) -> None:
        self.registry = registry

    def classify(
        self,
        comparison: VisualComparison,
        *,
        expected_change: bool,
        review_pixel_threshold: float = 0.01,
        review_perceptual_threshold: float = 0.01,
    ) -> VisualDiffDecision:
        hard = tuple(sorted(set(comparison.failed_assertions) & self.registry.hard_failure_codes))
        if hard:
            return VisualDiffDecision(
                VisualDiffClass.UNEXPECTED,
                f"hard visual failures: {', '.join(hard)}",
            )

        changed = comparison.pixel_difference_ratio > 0 or comparison.perceptual_difference > 0
        if expected_change:
            return VisualDiffDecision(
                VisualDiffClass.EXPECTED if changed else VisualDiffClass.REVIEW_REQUIRED,
                "expected visual change observed" if changed else "expected change produced no measurable visual difference",
            )

        if (
            comparison.pixel_difference_ratio > review_pixel_threshold
            or comparison.perceptual_difference > review_perceptual_threshold
        ):
            return VisualDiffDecision(
                VisualDiffClass.UNEXPECTED,
                "visual difference exceeds locked review thresholds",
            )

        if changed:
            return VisualDiffDecision(
                VisualDiffClass.REVIEW_REQUIRED,
                "small unapproved visual difference requires review",
            )

        return VisualDiffDecision(VisualDiffClass.EXPECTED, "no visual difference")
