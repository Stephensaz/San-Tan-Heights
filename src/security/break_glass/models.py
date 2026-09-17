from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

@dataclass(frozen=True)
class BreakGlassGrant:
    grant_id: UUID
    principal_id: str
    issued_by: str
    incident_id: UUID
    reason_code: str
    actions: tuple[str, ...]
    property_ids: tuple[str, ...]
    issued_at: datetime
    expires_at: datetime
    revoked_at: datetime|None=None

    def is_active(self, now: datetime) -> bool:
        return self.revoked_at is None and self.issued_at <= now < self.expires_at
