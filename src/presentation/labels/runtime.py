from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from src.presentation.package import PresentationAudience
from src.report_builder.labels.resolver import FriendlyLabelRegistry


@dataclass(frozen=True)
class FriendlyLabelResult:
    term_id: str
    audience: PresentationAudience
    label: str


@dataclass(frozen=True)
class FriendlyLabelRuntime:
    registry: FriendlyLabelRegistry

    @classmethod
    def from_repository(cls, root: str | Path) -> "FriendlyLabelRuntime":
        return cls(FriendlyLabelRegistry.from_repository(Path(root)))

    def resolve(self, term_id: str, audience: PresentationAudience) -> FriendlyLabelResult:
        if not term_id.strip():
            raise ValueError("term_id is required")
        try:
            label = self.registry.resolve(term_id, audience.value)
        except Exception as exc:
            raise ValueError(f"friendly label unavailable for {term_id} / {audience.value}") from exc
        if not label.strip():
            raise ValueError(f"friendly label unavailable for {term_id} / {audience.value}")
        return FriendlyLabelResult(term_id=term_id, audience=audience, label=label)

    def resolve_many(self, term_ids: tuple[str, ...], audience: PresentationAudience) -> tuple[FriendlyLabelResult, ...]:
        return tuple(self.resolve(term_id, audience) for term_id in term_ids)
