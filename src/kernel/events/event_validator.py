from __future__ import annotations
import json
from pathlib import Path
from jsonschema import Draft202012Validator

from .event_model import EventDraft
from .event_registry import EventRegistry

class EventValidationError(ValueError):
    pass

class EventValidator:
    def __init__(self, root: Path, registry: EventRegistry, reason_codes: frozenset[str]):
        self.root = root
        self.registry = registry
        self.reason_codes = reason_codes

    def validate(self, draft: EventDraft) -> None:
        try:
            definition = self.registry.get(draft.event_type)
        except KeyError as exc:
            raise EventValidationError(str(exc)) from exc
        if draft.source_system not in definition.producers:
            raise EventValidationError(
                f'producer {draft.source_system} not authorized for event {draft.event_type}'
            )
        if not draft.actor_type or not draft.actor_id:
            raise EventValidationError('actor_type and actor_id are required')
        if draft.reason_code is not None and draft.reason_code not in self.reason_codes:
            raise EventValidationError(f'unknown reason code: {draft.reason_code}')
        if not isinstance(draft.payload, dict):
            raise EventValidationError('event payload must be an object')
        schema_name = definition.schema_file or 'event-payload.schema.json'
        schema_path = self.root / 'schemas' / 'events' / schema_name
        if not schema_path.is_file():
            raise EventValidationError(f'missing event schema: {schema_name}')
        schema = json.loads(schema_path.read_text())
        errors = sorted(Draft202012Validator(schema).iter_errors(draft.payload), key=lambda e: list(e.path))
        if errors:
            raise EventValidationError(f'invalid payload for {draft.event_type}: {errors[0].message}')
