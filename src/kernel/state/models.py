from __future__ import annotations
from dataclasses import dataclass
from typing import Any

@dataclass(frozen=True)
class StateRecord:
    entity_id: Any
    state: str
    state_version: int
