from __future__ import annotations
from pathlib import Path

from src.kernel.registry import load_registry_bundle
from .models import GuardDefinition

class GuardRegistryError(ValueError):
    pass

class GuardRegistry:
    def __init__(self, definitions):
        defs=tuple(definitions)
        self._by_id={d.guard_id:d for d in defs}
        if len(self._by_id) != len(defs):
            raise GuardRegistryError('duplicate guard id')
        for d in defs:
            if not d.read_only:
                raise GuardRegistryError(f'guard must be read-only: {d.guard_id}')
            if not d.implementation:
                raise GuardRegistryError(f'guard missing implementation: {d.guard_id}')

    @classmethod
    def from_repository(cls, root: Path) -> 'GuardRegistry':
        bundle=load_registry_bundle(root)
        return cls(GuardDefinition(
            guard_id=item['id'],
            implementation=item['implementation'],
            read_only=bool(item.get('read_only', True)),
        ) for item in bundle.guards)

    def get(self, guard_id: str) -> GuardDefinition:
        try:
            return self._by_id[guard_id]
        except KeyError as exc:
            raise GuardRegistryError(f'unknown guard: {guard_id}') from exc

    def definitions(self) -> tuple[GuardDefinition, ...]:
        return tuple(self._by_id.values())
