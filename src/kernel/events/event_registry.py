from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from src.kernel.registry import load_registry_bundle

@dataclass(frozen=True)
class EventDefinition:
    event_id: str
    version: int
    producers: frozenset[str]
    schema_file: str | None = None
    topics: tuple[str, ...] = ('events',)

class EventRegistry:
    def __init__(self, definitions: Iterable[EventDefinition]):
        items = tuple(definitions)
        by_id = {x.event_id: x for x in items}
        if len(by_id) != len(items):
            raise ValueError('duplicate event definition')
        self._by_id = by_id

    @classmethod
    def from_repository(cls, root: Path) -> 'EventRegistry':
        bundle = load_registry_bundle(root)
        defs=[]
        for item in bundle.events:
            defs.append(EventDefinition(
                event_id=item['id'],
                version=int(item.get('version', 1)),
                producers=frozenset(item.get('producers') or []),
                schema_file=item.get('schema_file'),
                topics=tuple(item.get('topics') or ['events']),
            ))
        return cls(defs)

    def get(self, event_id: str) -> EventDefinition:
        try:
            return self._by_id[event_id]
        except KeyError as exc:
            raise KeyError(f'unknown event type: {event_id}') from exc

    def __contains__(self, event_id: str) -> bool:
        return event_id in self._by_id
