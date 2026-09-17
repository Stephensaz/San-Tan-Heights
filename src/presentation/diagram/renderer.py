from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from html import escape
from typing import Iterable

from src.presentation.diagram.grammar import DiagramGrammarRuntime, DiagramGrammarSpec
from src.presentation.tokens import DesignTokenRegistry
from src.shared.canonical_json import canonical_json

_NOTICE = "Schematic relationship diagram — not a map and not to scale."
_RELATION_LABELS = {
    "FRONTS": "Front relationship",
    "BACKS_TO": "Rear relationship",
    "SIDES_TO": "Side relationship",
    "TOUCHES": "Touches",
    "ADJACENT_TO": "Adjacent context",
    "ACROSS_FROM": "Across-from context",
    "ORIENTED_TOWARD": "Orientation context",
}
_ZONE_CYCLE = ("CONTEXT_LEFT", "CONTEXT_RIGHT", "CONTEXT_TOP", "CONTEXT_BOTTOM")
_ZONE_POSITIONS = {
    "FRONT": (400, 395),
    "REAR": (400, 95),
    "SIDE_LEFT": (145, 245),
    "SIDE_RIGHT": (655, 245),
    "CONTEXT_LEFT": (145, 95),
    "CONTEXT_RIGHT": (655, 95),
    "CONTEXT_TOP": (145, 395),
    "CONTEXT_BOTTOM": (655, 395),
}


@dataclass(frozen=True)
class SchematicRelationshipPlacement:
    relationship_id: str
    relationship_type: str
    target_entity_id: str
    target_label: str
    zone: str
    source_finding_id: str


@dataclass(frozen=True)
class SchematicDiagramRender:
    diagram_id: str
    subject_label: str
    placements: tuple[SchematicRelationshipPlacement, ...]
    notice: str
    svg: str

    def canonical_payload(self) -> dict[str, object]:
        return {
            "diagram_id": self.diagram_id,
            "subject_label": self.subject_label,
            "placements": [placement.__dict__ for placement in self.placements],
            "notice": self.notice,
            "svg": self.svg,
        }

    @property
    def fingerprint(self) -> str:
        return sha256(canonical_json(self.canonical_payload()).encode("utf-8")).hexdigest()


class LotContextDiagramRenderer:
    def __init__(self, *, grammar: DiagramGrammarRuntime, tokens: DesignTokenRegistry) -> None:
        self.grammar = grammar
        self.tokens = tokens

    def render(self, spec: DiagramGrammarSpec) -> SchematicDiagramRender:
        spec = self.grammar.validate(spec)
        entities = {entity.entity_id: entity for entity in spec.entities}
        subject = next(entity for entity in spec.entities if entity.entity_type == "SUBJECT_LOT")
        subject_label = subject.label or "Subject Homesite"

        side_toggle = 0
        context_index = 0
        placements: list[SchematicRelationshipPlacement] = []
        for relation in sorted(spec.relationships, key=lambda item: item.relationship_id):
            if relation.relationship_type == "FRONTS":
                zone = "FRONT"
            elif relation.relationship_type == "BACKS_TO":
                zone = "REAR"
            elif relation.relationship_type == "SIDES_TO":
                zone = "SIDE_LEFT" if side_toggle % 2 == 0 else "SIDE_RIGHT"
                side_toggle += 1
            else:
                zone = _ZONE_CYCLE[context_index % len(_ZONE_CYCLE)]
                context_index += 1

            target = entities[relation.target_entity_id]
            placements.append(
                SchematicRelationshipPlacement(
                    relationship_id=relation.relationship_id,
                    relationship_type=relation.relationship_type,
                    target_entity_id=target.entity_id,
                    target_label=target.label or target.entity_type.replace("_", " ").title(),
                    zone=zone,
                    source_finding_id=relation.source_finding_id,
                )
            )

        render = SchematicDiagramRender(
            diagram_id=spec.diagram_id,
            subject_label=subject_label,
            placements=tuple(placements),
            notice=_NOTICE,
            svg=self._svg(subject_label, placements),
        )
        return render

    def _svg(self, subject_label: str, placements: Iterable[SchematicRelationshipPlacement]) -> str:
        colors = self.tokens.colors
        border = colors["border_default"]
        surface = colors["surface_primary"]
        subtle = colors["surface_subtle"]
        text = colors["text_primary"]
        muted = colors["text_muted"]
        accent = colors["accent_primary"]

        parts = [
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 500" role="img">',
            f'<rect x="0" y="0" width="800" height="500" fill="{surface}"/>',
            f'<rect x="300" y="180" width="200" height="140" rx="12" fill="{subtle}" stroke="{accent}" stroke-width="3"/>',
            f'<text x="400" y="245" text-anchor="middle" font-size="18" fill="{text}">{escape(subject_label)}</text>',
            f'<text x="400" y="270" text-anchor="middle" font-size="13" fill="{muted}">Subject homesite</text>',
        ]

        for placement in placements:
            x, y = _ZONE_POSITIONS[placement.zone]
            relation_label = _RELATION_LABELS[placement.relationship_type]
            parts.extend(
                [
                    f'<rect x="{x - 105}" y="{y - 42}" width="210" height="84" rx="8" fill="{surface}" stroke="{border}"/>',
                    f'<text x="{x}" y="{y - 8}" text-anchor="middle" font-size="14" fill="{text}">{escape(placement.target_label)}</text>',
                    f'<text x="{x}" y="{y + 16}" text-anchor="middle" font-size="12" fill="{muted}">{escape(relation_label)}</text>',
                ]
            )

        parts.extend(
            [
                f'<text x="400" y="480" text-anchor="middle" font-size="11" fill="{muted}">{escape(_NOTICE)}</text>',
                "</svg>",
            ]
        )
        return "".join(parts)
