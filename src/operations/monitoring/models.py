from dataclasses import dataclass
from datetime import datetime
from uuid import UUID
@dataclass(frozen=True)
class IntegrityFinding:
    rule_id: str
    entity_type: str
    entity_id: UUID | str
    status: str
    detail: str
