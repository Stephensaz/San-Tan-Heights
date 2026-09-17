from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from hashlib import sha256
from types import MappingProxyType
from typing import Mapping, Any
import re

from src.shared.canonical_json import canonical_json

_ID_RE = re.compile(r"^[a-z][a-z0-9_-]{0,63}$")
_FORBIDDEN_PROPS = {
    "score", "ranking", "rank", "valuation", "premium", "desirability",
    "audience_override", "publication_override", "confidence_override",
}


class PrimitiveKind(str, Enum):
    TEXT = "TEXT"
    STACK = "STACK"
    CARD = "CARD"
    DIVIDER = "DIVIDER"
    DISCLOSURE = "DISCLOSURE"


class TextRole(str, Enum):
    BODY = "BODY"
    HEADING = "HEADING"
    CAPTION = "CAPTION"
    LABEL = "LABEL"


@dataclass(frozen=True)
class ComponentPrimitive:
    component_id: str
    kind: PrimitiveKind
    props: Mapping[str, Any]
    children: tuple["ComponentPrimitive", ...] = ()

    def __post_init__(self) -> None:
        if not _ID_RE.fullmatch(self.component_id):
            raise ValueError("component_id must be stable lowercase slug")
        props = dict(self.props)
        forbidden = sorted(_FORBIDDEN_PROPS.intersection(props))
        if forbidden:
            raise ValueError(f"semantic override properties are forbidden: {forbidden}")
        object.__setattr__(self, "props", MappingProxyType(props))
        object.__setattr__(self, "children", tuple(self.children))

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "component_id": self.component_id,
            "kind": self.kind.value,
            "props": dict(self.props),
            "children": [child.canonical_payload() for child in self.children],
        }

    @property
    def fingerprint(self) -> str:
        return sha256(canonical_json(self.canonical_payload()).encode("utf-8")).hexdigest()


def text(component_id: str, approved_text: str, *, role: TextRole = TextRole.BODY) -> ComponentPrimitive:
    value = approved_text.strip()
    if not value:
        raise ValueError("approved_text is required")
    return ComponentPrimitive(component_id, PrimitiveKind.TEXT, {"text": value, "role": role.value})


def stack(component_id: str, *children: ComponentPrimitive, gap_token: str = "md") -> ComponentPrimitive:
    if not children:
        raise ValueError("stack requires at least one child")
    return ComponentPrimitive(component_id, PrimitiveKind.STACK, {"gap_token": gap_token}, tuple(children))


def card(component_id: str, *children: ComponentPrimitive, surface_token: str = "surface_primary") -> ComponentPrimitive:
    if not children:
        raise ValueError("card requires at least one child")
    return ComponentPrimitive(component_id, PrimitiveKind.CARD, {"surface_token": surface_token}, tuple(children))


def divider(component_id: str, border_token: str = "border_default") -> ComponentPrimitive:
    return ComponentPrimitive(component_id, PrimitiveKind.DIVIDER, {"border_token": border_token})


def disclosure(component_id: str, label: str, *children: ComponentPrimitive) -> ComponentPrimitive:
    clean = label.strip()
    if not clean or not children:
        raise ValueError("disclosure requires label and content")
    return ComponentPrimitive(component_id, PrimitiveKind.DISCLOSURE, {"label": clean}, tuple(children))
