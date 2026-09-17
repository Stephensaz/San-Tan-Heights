from __future__ import annotations
from pathlib import Path
from typing import Any
import json
from jsonschema import Draft202012Validator, RefResolver

class CanonicalReportSchemaError(ValueError):
    pass

class CanonicalReportSchema:
    ROOT_FILE = 'canonical-report.schema.json'
    FORBIDDEN_PRESENTATION_KEYS = frozenset({'css','style','styles','x','y','width','height','pixels','page_x','page_y'})

    def __init__(self, schema_dir: Path):
        self.schema_dir = Path(schema_dir)
        root_path = self.schema_dir / self.ROOT_FILE
        self.schema = json.loads(root_path.read_text())
        store = {}
        for schema_path in self.schema_dir.glob('*.schema.json'):
            loaded = json.loads(schema_path.read_text())
            store[schema_path.name] = loaded
            store[schema_path.as_uri()] = loaded
        base_uri = self.schema_dir.as_uri().rstrip('/') + '/'
        self.validator = Draft202012Validator(
            self.schema,
            resolver=RefResolver(base_uri=base_uri, referrer=self.schema, store=store),
        )

    @classmethod
    def from_repository(cls, root: Path) -> 'CanonicalReportSchema':
        return cls(Path(root) / 'schemas' / 'reports')

    def validate(self, payload: dict[str, Any]) -> None:
        self._reject_presentation_keys(payload)
        errors = sorted(self.validator.iter_errors(payload), key=lambda e: list(e.absolute_path))
        if errors:
            err = errors[0]
            path = '.'.join(str(x) for x in err.absolute_path) or '<root>'
            raise CanonicalReportSchemaError(f'{path}: {err.message}')
        self._validate_cross_references(payload)

    def _reject_presentation_keys(self, value: Any, path: str = '<root>') -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                if key.lower() in self.FORBIDDEN_PRESENTATION_KEYS:
                    raise CanonicalReportSchemaError(f'presentation-only key forbidden at {path}: {key}')
                self._reject_presentation_keys(child, f'{path}.{key}')
        elif isinstance(value, list):
            for idx, child in enumerate(value):
                self._reject_presentation_keys(child, f'{path}[{idx}]')

    def _validate_cross_references(self, payload: dict[str, Any]) -> None:
        property_id = payload['property_identity']['property_id']
        if property_id != payload['metadata']['property_id']:
            raise CanonicalReportSchemaError('property identity does not match metadata property_id')
        if payload['lineage']['snapshot_id'] != payload['metadata']['snapshot_id']:
            raise CanonicalReportSchemaError('lineage snapshot_id does not match metadata snapshot_id')
        sections = {x['section_id']: x for x in payload['sections']}
        if len(sections) != len(payload['sections']):
            raise CanonicalReportSchemaError('duplicate section_id')
        orders = [x['order'] for x in payload['sections']]
        if orders != sorted(orders) or len(set(orders)) != len(orders):
            raise CanonicalReportSchemaError('section order must be unique and ascending')
        findings = {x['finding_id'] for x in payload['findings']}
        cards = {x['card_id']: x for x in payload['cards']}
        if len(cards) != len(payload['cards']):
            raise CanonicalReportSchemaError('duplicate card_id')
        for finding in payload['findings']:
            if finding['section_id'] not in sections:
                raise CanonicalReportSchemaError(f"finding references unknown section: {finding['section_id']}")
        for card in payload['cards']:
            if card['section_id'] not in sections:
                raise CanonicalReportSchemaError(f"card references unknown section: {card['section_id']}")
            unknown = set(card['finding_ids']) - findings
            if unknown:
                raise CanonicalReportSchemaError(f'card references unknown findings: {sorted(unknown)}')
        for section in payload['sections']:
            unknown = set(section['card_ids']) - set(cards)
            if unknown:
                raise CanonicalReportSchemaError(f'section references unknown cards: {sorted(unknown)}')
