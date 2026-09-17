from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from html import escape
from typing import Iterable

from src.presentation.diagram.renderer import SchematicDiagramRender, SchematicRelationshipPlacement
from src.shared.canonical_json import canonical_json

_RELATION_PHRASES = {
    "FRONTS": "Front relationship",
    "BACKS_TO": "Rear relationship",
    "SIDES_TO": "Side relationship",
    "TOUCHES": "Touches",
    "ADJACENT_TO": "Adjacent context",
    "ACROSS_FROM": "Across-from context",
    "ORIENTED_TOWARD": "Orientation context",
}

_ZONE_ORDER = {
    "FRONT": 10,
    "REAR": 20,
    "SIDE_LEFT": 30,
    "SIDE_RIGHT": 40,
    "CONTEXT_LEFT": 50,
    "CONTEXT_RIGHT": 60,
    "CONTEXT_TOP": 70,
    "CONTEXT_BOTTOM": 80,
}


@dataclass(frozen=True)
class AccessibleRelationshipItem:
    relationship_id: str
    relationship_type: str
    target_label: str
    semantic_zone: str
    text: str
    source_finding_id: str

    def canonical_payload(self) -> dict[str, str]:
        return {
            "relationship_id": self.relationship_id,
            "relationship_type": self.relationship_type,
            "target_label": self.target_label,
            "semantic_zone": self.semantic_zone,
            "text": self.text,
            "source_finding_id": self.source_finding_id,
        }


@dataclass(frozen=True)
class AccessibleDiagramView:
    diagram_id: str
    subject_label: str
    short_description: str
    long_description: str
    reading_order: tuple[AccessibleRelationshipItem, ...]
    nonvisual_equivalent: tuple[str, ...]
    notice: str
    accessible_svg: str

    def canonical_payload(self) -> dict[str, object]:
        return {
            "diagram_id": self.diagram_id,
            "subject_label": self.subject_label,
            "short_description": self.short_description,
            "long_description": self.long_description,
            "reading_order": [item.canonical_payload() for item in self.reading_order],
            "nonvisual_equivalent": list(self.nonvisual_equivalent),
            "notice": self.notice,
            "accessible_svg": self.accessible_svg,
        }

    @property
    def fingerprint(self) -> str:
        return sha256(canonical_json(self.canonical_payload()).encode("utf-8")).hexdigest()


class DiagramAccessibilityLayer:
    """Deterministic accessibility projection for governed schematic diagrams.

    The layer may describe only relationships already present in the renderer output.
    It cannot add geographic direction, distance, scale, desirability, value, or any
    other property interpretation.
    """

    def build(self, render: SchematicDiagramRender) -> AccessibleDiagramView:
        if not render.diagram_id.strip() or not render.subject_label.strip():
            raise ValueError("diagram_id and subject_label are required")
        if not render.notice.strip():
            raise ValueError("diagram notice is required")

        ordered = tuple(sorted(render.placements, key=self._sort_key))
        items = tuple(self._item(placement) for placement in ordered)

        short = f"Schematic relationship diagram for {render.subject_label}."
        relationship_sentences = tuple(item.text for item in items)
        long_parts = (short,) + relationship_sentences + (render.notice,)
        long_description = " ".join(long_parts)
        nonvisual = (f"Subject: {render.subject_label}.",) + relationship_sentences + (render.notice,)

        title_id = f"{render.diagram_id}-title"
        desc_id = f"{render.diagram_id}-desc"
        accessible_svg = self._decorate_svg(
            svg=render.svg,
            title_id=title_id,
            desc_id=desc_id,
            title=short,
            description=long_description,
        )

        return AccessibleDiagramView(
            diagram_id=render.diagram_id,
            subject_label=render.subject_label,
            short_description=short,
            long_description=long_description,
            reading_order=items,
            nonvisual_equivalent=nonvisual,
            notice=render.notice,
            accessible_svg=accessible_svg,
        )

    @staticmethod
    def _sort_key(placement: SchematicRelationshipPlacement) -> tuple[int, str]:
        try:
            order = _ZONE_ORDER[placement.zone]
        except KeyError as exc:
            raise ValueError(f"unsupported semantic diagram zone: {placement.zone}") from exc
        return order, placement.relationship_id

    @staticmethod
    def _item(placement: SchematicRelationshipPlacement) -> AccessibleRelationshipItem:
        try:
            phrase = _RELATION_PHRASES[placement.relationship_type]
        except KeyError as exc:
            raise ValueError(f"unsupported accessible relationship type: {placement.relationship_type}") from exc
        target = placement.target_label.strip()
        if not target:
            raise ValueError("accessible relationship target label cannot be blank")
        text = f"{phrase}: {target}."
        return AccessibleRelationshipItem(
            relationship_id=placement.relationship_id,
            relationship_type=placement.relationship_type,
            target_label=target,
            semantic_zone=placement.zone,
            text=text,
            source_finding_id=placement.source_finding_id,
        )

    @staticmethod
    def _decorate_svg(*, svg: str, title_id: str, desc_id: str, title: str, description: str) -> str:
        marker = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 500" role="img">'
        if not svg.startswith(marker):
            raise ValueError("diagram SVG does not match the certified renderer contract")
        opening = (
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 500" role="img" '
            f'aria-labelledby="{escape(title_id)} {escape(desc_id)}">'
            f'<title id="{escape(title_id)}">{escape(title)}</title>'
            f'<desc id="{escape(desc_id)}">{escape(description)}</desc>'
        )
        return opening + svg[len(marker):]
