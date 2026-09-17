from __future__ import annotations
from .transition_registry import TransitionRegistry

class TransitionResolver:
    def __init__(self, registry: TransitionRegistry):
        self.registry=registry

    def by_id(self, transition_id: str):
        return self.registry.get(transition_id)

    def by_states(self, entity_type: str, state_dimension: str, from_state: str, to_state: str):
        return self.registry.resolve(entity_type,state_dimension,from_state,to_state)
