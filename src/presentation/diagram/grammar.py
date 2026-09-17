from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import re
from types import MappingProxyType
from typing import Mapping

import yaml

from src.shared.canonical_json import canonical_json

_SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_EXPECTED_ID = "STH-DIAGRAM-GRAMMAR-v1.0"
_EXPECTED_VERSION = "1.0.0"
_EXPECTED_STATUS = "LOCKED"
_EXPECTED_KIND = "SCHEMATIC_RELATIONSHIP"


@dataclass(frozen=True)
class DiagramEntity:
    entity_id: str
    entity_type: str
    label: str | None
    source_finding_id: str

    def __post_init__(self) -> None:
        if not _SLUG.fullmatch(self.entity_id):
            raise ValueError("diagram entity_id must be a lowercase slug")
        if not self.source_finding_id.strip():
            raise ValueError("diagram entity requires a governed source_finding_id")
        if self.label is not None and not self.label.strip():
            raise ValueError("diagram entity label cannot be blank")


@dataclass(frozen=True)
class DiagramRelationship:
    relationship_id: str
    relationship_type: str
    source_entity_id: str
    target_entity_id: str
    source_finding_id: str

    def __post_init__(self) -> None:
        if not _SLUG.fullmatch(self.relationship_id):
            raise ValueError("diagram relationship_id must be a lowercase slug")
        if self.source_entity_id == self.target_entity_id:
            raise ValueError("diagram relationship cannot point to itself")
        if not self.source_finding_id.strip():
            raise ValueError("diagram relationship requires a governed source_finding_id")


@dataclass(frozen=True)
class DiagramGrammarSpec:
    diagram_id: str
    entities: tuple[DiagramEntity, ...]
    relationships: tuple[DiagramRelationship, ...]

    def __post_init__(self) -> None:
        if not _SLUG.fullmatch(self.diagram_id):
            raise ValueError("diagram_id must be a lowercase slug")
        object.__setattr__(self, "entities", tuple(self.entities))
        object.__setattr__(self, "relationships", tuple(self.relationships))

    def canonical_payload(self) -> dict[str, object]:
        return {
            "diagram_id": self.diagram_id,
            "entities": [
                {
                    "entity_id": entity.entity_id,
                    "entity_type": entity.entity_type,
                    "label": entity.label,
                    "source_finding_id": entity.source_finding_id,
                }
                for entity in self.entities
            ],
            "relationships": [
                {
                    "relationship_id": relation.relationship_id,
                    "relationship_type": relation.relationship_type,
                    "source_entity_id": relation.source_entity_id,
                    "target_entity_id": relation.target_entity_id,
                    "source_finding_id": relation.source_finding_id,
                }
                for relation in self.relationships
            ],
        }

    @property
    def fingerprint(self) -> str:
        return sha256(canonical_json(self.canonical_payload()).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class DiagramGrammarRegistry:
    grammar_id: str
    version: str
    status: str
    diagram_kind: str
    entity_types: frozenset[str]
    relationship_types: frozenset[str]
    rules: Mapping[str, bool]
    fingerprint: str

    @classmethod
    def load(cls, path: str | Path) -> "DiagramGrammarRegistry":
        raw = yaml.safe_load(Path(path).read_text())
        if not isinstance(raw, dict):
            raise ValueError("diagram grammar registry must be an object")
        if raw.get("grammar_id") != _EXPECTED_ID:
            raise ValueError("unexpected diagram grammar id")
        if raw.get("version") != _EXPECTED_VERSION:
            raise ValueError("unexpected diagram grammar version")
        if raw.get("status") != _EXPECTED_STATUS:
            raise ValueError("diagram grammar must be LOCKED")
        if raw.get("diagram_kind") != _EXPECTED_KIND:
            raise ValueError("unexpected diagram grammar kind")

        entities = raw.get("entity_types") or {}
        relationships = raw.get("relationship_types") or {}
        rules = raw.get("rules") or {}
        if not isinstance(entities, dict) or not entities:
            raise ValueError("diagram grammar entity_types cannot be empty")
        if not isinstance(relationships, dict) or not relationships:
            raise ValueError("diagram grammar relationship_types cannot be empty")
        if not isinstance(rules, dict):
            raise ValueError("diagram grammar rules must be an object")

        expected_rules = {
            "require_single_subject": True,
            "require_governed_source_reference": True,
            "allow_coordinates": False,
            "allow_distances": False,
            "allow_value_claims": False,
            "allow_unreferenced_entities": False,
            "allow_unreferenced_relationships": False,
        }
        if rules != expected_rules:
            raise ValueError("diagram grammar rules do not match locked safety contract")

        payload = {
            "grammar_id": _EXPECTED_ID,
            "version": _EXPECTED_VERSION,
            "status": _EXPECTED_STATUS,
            "diagram_kind": _EXPECTED_KIND,
            "entity_types": sorted(str(key) for key in entities),
            "relationship_types": sorted(str(key) for key in relationships),
            "rules": expected_rules,
        }
        fingerprint = sha256(canonical_json(payload).encode("utf-8")).hexdigest()
        return cls(
            grammar_id=_EXPECTED_ID,
            version=_EXPECTED_VERSION,
            status=_EXPECTED_STATUS,
            diagram_kind=_EXPECTED_KIND,
            entity_types=frozenset(payload["entity_types"]),
            relationship_types=frozenset(payload["relationship_types"]),
            rules=MappingProxyType(dict(expected_rules)),
            fingerprint=fingerprint,
        )


class DiagramGrammarRuntime:
    def __init__(self, registry: DiagramGrammarRegistry) -> None:
        self.registry = registry

    def validate(self, spec: DiagramGrammarSpec) -> DiagramGrammarSpec:
        entity_ids: set[str] = set()
        subject_count = 0
        for entity in spec.entities:
            if entity.entity_id in entity_ids:
                raise ValueError("diagram entity IDs must be unique")
            entity_ids.add(entity.entity_id)
            if entity.entity_type not in self.registry.entity_types:
                raise ValueError(f"unsupported diagram entity type: {entity.entity_type}")
            if entity.entity_type == "SUBJECT_LOT":
                subject_count += 1

        if self.registry.rules["require_single_subject"] and subject_count != 1:
            raise ValueError("diagram requires exactly one SUBJECT_LOT")

        relation_ids: set[str] = set()
        for relation in spec.relationships:
            if relation.relationship_id in relation_ids:
                raise ValueError("diagram relationship IDs must be unique")
            relation_ids.add(relation.relationship_id)
            if relation.relationship_type not in self.registry.relationship_types:
                raise ValueError(f"unsupported diagram relationship type: {relation.relationship_type}")
            if relation.source_entity_id not in entity_ids or relation.target_entity_id not in entity_ids:
                raise ValueError("diagram relationship references unknown entity")

        return spec
