from dataclasses import dataclass
from datetime import datetime
from uuid import UUID
@dataclass(frozen=True)
class SecurityAuditEvent:
    security_event_id: UUID
    event_type: str
    occurred_at: datetime
    actor_type: str
    actor_id: str
    outcome: str
    reason_code: str
    property_id: UUID|None=None
    incident_id: UUID|None=None
    correlation_id: UUID|None=None
    evidence_hash: str|None=None
