from __future__ import annotations
from .state_adapter import StateAdapter, StateAdapterError

class StateAdapterRegistry:
    def __init__(self):
        self._adapters={}

    def register(self, adapter: StateAdapter) -> None:
        key=(adapter.entity_type, adapter.state_dimension)
        if key in self._adapters:
            raise StateAdapterError(f'duplicate state adapter: {key}')
        self._adapters[key]=adapter

    def get(self, entity_type: str, state_dimension: str) -> StateAdapter:
        key=(entity_type,state_dimension)
        try:
            return self._adapters[key]
        except KeyError as exc:
            raise StateAdapterError(f'no state adapter registered: {key}') from exc
