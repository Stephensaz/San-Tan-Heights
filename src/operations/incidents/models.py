from __future__ import annotations
from dataclasses import dataclass
from uuid import UUID

@dataclass(frozen=True)
class Incident:
    incident_id: UUID
    incident_key: str
    incident_type: str
    severity: str
    incident_state: str
    reason_code: str
    property_id: UUID|None=None
    report_variant: str|None=None
    channel: str|None=None
    release_id: UUID|None=None
    source_rule_id: str|None=None
    source_entity_type: str|None=None
    source_entity_id: str|None=None
    correlation_id: UUID|None=None

@dataclass(frozen=True)
class IncidentTransition:
    status: str
    from_state: str
    to_state: str
