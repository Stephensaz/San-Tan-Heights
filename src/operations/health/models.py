from __future__ import annotations
from dataclasses import dataclass, field
from typing import Mapping
from uuid import UUID

HEALTH_LEVELS = ('HEALTHY','DEGRADED','CRITICAL','UNKNOWN')
_SEVERITY = {'UNKNOWN':0,'HEALTHY':1,'DEGRADED':2,'CRITICAL':3}

@dataclass(frozen=True)
class HealthSignal:
    code: str
    status: str
    count: int = 0
    detail: str | None = None
    def __post_init__(self):
        if self.status not in HEALTH_LEVELS: raise ValueError('unsupported health status')
        if self.count < 0: raise ValueError('count must be non-negative')
        if not self.code.strip(): raise ValueError('signal code cannot be blank')

@dataclass(frozen=True)
class PropertyHealth:
    property_id: UUID
    status: str
    signals: tuple[HealthSignal,...] = field(default_factory=tuple)

@dataclass(frozen=True)
class FleetHealth:
    status: str
    total_properties: int
    counts: Mapping[str,int]
    signal_counts: Mapping[str,int]


def worst_status(statuses):
    values=tuple(statuses)
    if not values: return 'UNKNOWN'
    return max(values, key=lambda s:_SEVERITY[s])
