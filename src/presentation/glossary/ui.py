from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from typing import Iterable

from src.presentation.package import PresentationAudience
from src.report_builder.findings.selector import FindingSelection
from src.report_builder.glossary.resolver import GlossaryEntry, GlossaryResolver
from src.shared.canonical_json import canonical_json


@dataclass(frozen=True)
class ConsumerGlossaryItem:
    term_id: str
    label: str
    definition: str
    glossary_version: str

    @classmethod
    def from_entry(cls, entry: GlossaryEntry) -> "ConsumerGlossaryItem":
        for name, value in (("term_id", entry.term_id), ("label", entry.label), ("definition", entry.definition), ("glossary_version", entry.glossary_version)):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"glossary {name} is required")
        return cls(entry.term_id, entry.label, entry.definition, entry.glossary_version)

    def canonical_payload(self) -> dict[str, str]:
        return {
            "term_id": self.term_id,
            "label": self.label,
            "definition": self.definition,
            "glossary_version": self.glossary_version,
        }


@dataclass(frozen=True)
class ConsumerGlossaryPanel:
    audience: PresentationAudience
    title: str
    source_registry_id: str
    source_version: str
    items: tuple[ConsumerGlossaryItem, ...]

    def canonical_payload(self) -> dict[str, object]:
        return {
            "audience": self.audience.value,
            "title": self.title,
            "source_registry_id": self.source_registry_id,
            "source_version": self.source_version,
            "items": [item.canonical_payload() for item in self.items],
        }

    @property
    def fingerprint(self) -> str:
        return sha256(canonical_json(self.canonical_payload()).encode("utf-8")).hexdigest()


class ConsumerGlossaryUi:
    """Project governed glossary entries into a consumer-facing panel.

    Definitions come only from the existing governed GlossaryResolver. This layer
    never authors, expands, rewrites, or infers glossary definitions.
    """

    def build(
        self,
        resolver: GlossaryResolver,
        selections: Iterable[FindingSelection],
        audience: PresentationAudience,
    ) -> ConsumerGlossaryPanel:
        if not isinstance(resolver, GlossaryResolver):
            raise ValueError("consumer glossary requires the governed GlossaryResolver")
        if not isinstance(audience, PresentationAudience):
            raise ValueError("audience must be a PresentationAudience")

        entries = resolver.resolve(tuple(selections), audience.value)
        items = tuple(ConsumerGlossaryItem.from_entry(entry) for entry in entries)
        term_ids = tuple(item.term_id for item in items)
        if len(term_ids) != len(set(term_ids)):
            raise ValueError("consumer glossary contains duplicate term ids")
        if any(item.glossary_version != resolver.version for item in items):
            raise ValueError("consumer glossary entry version mismatch")

        return ConsumerGlossaryPanel(
            audience=audience,
            title="Glossary",
            source_registry_id=resolver.registry_id,
            source_version=resolver.version,
            items=items,
        )
