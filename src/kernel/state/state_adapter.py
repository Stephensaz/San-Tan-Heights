from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any
from .models import StateRecord

class StateAdapterError(RuntimeError):
    pass

class EntityNotFoundError(StateAdapterError):
    pass

class StateConflictError(StateAdapterError):
    pass

class StateAdapter(ABC):
    entity_type: str
    state_dimension: str

    @abstractmethod
    def get_current_state(self, cursor, entity_id: Any) -> StateRecord | None: ...

    @abstractmethod
    def lock_current_state(self, cursor, entity_id: Any) -> StateRecord | None: ...

    @abstractmethod
    def apply_state(self, cursor, entity_id: Any, expected_state: str, target_state: str, expected_version: int) -> StateRecord: ...
