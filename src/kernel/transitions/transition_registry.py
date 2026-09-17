from __future__ import annotations
from pathlib import Path

from src.kernel.registry import load_registry_bundle
from .transition_model import TransitionDefinition

class TransitionRegistryError(ValueError):
    pass

class TransitionRegistry:
    def __init__(self, definitions):
        defs=tuple(definitions)
        self._by_id={d.transition_id:d for d in defs}
        if len(self._by_id) != len(defs):
            raise TransitionRegistryError('duplicate transition id')
        self._by_signature={}
        for d in defs:
            key=(d.entity_type,d.state_dimension,d.from_state,d.to_state)
            if key in self._by_signature:
                raise TransitionRegistryError(f'ambiguous transition signature: {key}')
            self._by_signature[key]=d

    @classmethod
    def from_repository(cls, root: Path) -> 'TransitionRegistry':
        bundle=load_registry_bundle(root)
        defs=[]
        for item in bundle.transitions:
            defs.append(TransitionDefinition(
                transition_id=item['transition_id'],
                entity_type=item['entity_type'],
                state_dimension=item['state_dimension'],
                from_state=item['from_state'],
                to_state=item['to_state'],
                allowed_callers=frozenset(item.get('allowed_callers') or []),
                required_guards=tuple(item.get('required_guards') or []),
                emitted_events=tuple(item.get('emitted_events') or []),
                rejection_event=item.get('rejection_event'),
                reason_code=item.get('reason_code'),
            ))
        return cls(defs)

    def get(self, transition_id: str) -> TransitionDefinition:
        try:
            return self._by_id[transition_id]
        except KeyError as exc:
            raise TransitionRegistryError(f'unknown transition: {transition_id}') from exc

    def resolve(self, entity_type: str, state_dimension: str, from_state: str, to_state: str) -> TransitionDefinition:
        key=(entity_type,state_dimension,from_state,to_state)
        try:
            return self._by_signature[key]
        except KeyError as exc:
            raise TransitionRegistryError(f'transition not allowed: {key}') from exc
