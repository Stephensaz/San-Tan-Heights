from __future__ import annotations
from uuid import UUID
from typing import Protocol
from .models import GovernedPropertyState
from .validator import GovernedStateValidator

class GovernedStateProvider(Protocol):
    def get_governed_property_state(self, property_id: UUID) -> dict: ...

class GovernedStateClient:
    """Validated anti-corruption boundary around an upstream governed-state provider."""
    def __init__(self, provider: GovernedStateProvider, validator: GovernedStateValidator | None = None):
        self.provider=provider; self.validator=validator or GovernedStateValidator()
    def get(self, property_id: UUID) -> GovernedPropertyState:
        raw=self.provider.get_governed_property_state(property_id)
        state=self.validator.validate(raw)
        if state.property_id != property_id:
            raise ValueError('governed-state provider returned the wrong property')
        return state
