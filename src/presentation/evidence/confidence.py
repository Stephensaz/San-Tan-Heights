from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256

from src.presentation.audience import AudiencePresentationPolicies
from src.presentation.evidence.disclosure import EvidenceDisclosureSet
from src.presentation.package import PresentationAudience
from src.shared.canonical_json import canonical_json


@dataclass(frozen=True)
class ConfidenceLimitationItem:
    finding_id: str
    label: str
    confidence_text: str | None
    limitation_text: str | None

    def canonical_payload(self) -> dict[str, object]:
        return {
            "finding_id": self.finding_id,
            "label": self.label,
            "confidence_text": self.confidence_text,
            "limitation_text": self.limitation_text,
        }


@dataclass(frozen=True)
class ConfidenceLimitationSet:
    audience: str
    visibility_mode: str
    items: tuple[ConfidenceLimitationItem, ...]

    def canonical_payload(self) -> dict[str, object]:
        return {
            "audience": self.audience,
            "visibility_mode": self.visibility_mode,
            "items": [item.canonical_payload() for item in self.items],
        }

    @property
    def fingerprint(self) -> str:
        return sha256(canonical_json(self.canonical_payload()).encode("utf-8")).hexdigest()


class ConfidenceLimitationBuilder:
    """Project approved confidence and limitation wording into UI components.

    The builder consumes the accepted M8-015 disclosure set. It never derives a
    score, translates confidence into a new label, or invents missing wording.
    """

    def __init__(self, policies: AudiencePresentationPolicies) -> None:
        self.policies = policies

    def build(
        self,
        disclosure: EvidenceDisclosureSet,
        *,
        audience: PresentationAudience,
    ) -> ConfidenceLimitationSet:
        if disclosure.audience != audience.value:
            raise ValueError("confidence/limitation disclosure audience mismatch")

        policy = self.policies.for_audience(audience)
        items: list[ConfidenceLimitationItem] = []
        for item in disclosure.items:
            confidence = self._clean_optional(item.confidence_label)
            limitation = self._clean_optional(item.limitation)
            if confidence is None and limitation is None:
                continue
            items.append(
                ConfidenceLimitationItem(
                    finding_id=item.finding_id,
                    label=item.label,
                    confidence_text=confidence,
                    limitation_text=limitation,
                )
            )

        return ConfidenceLimitationSet(
            audience=audience.value,
            visibility_mode=policy.confidence_visibility,
            items=tuple(items),
        )

    @staticmethod
    def _clean_optional(value: str | None) -> str | None:
        if value is None:
            return None
        if not isinstance(value, str) or not value.strip():
            raise ValueError("confidence/limitation text cannot be blank")
        return value
