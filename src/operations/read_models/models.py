from dataclasses import dataclass
from uuid import UUID
@dataclass(frozen=True)
class PropertyOperationsRow:
    property_id: UUID
    health_status: str
    current_snapshot_id: UUID | None
    open_job_count: int
    pointer_violation_count: int
    orphan_count: int
    stuck_job_count: int
    release_failure_count: int
@dataclass(frozen=True)
class FleetOperationsRow:
    total_properties: int
    healthy_count: int
    degraded_count: int
    critical_count: int
    unknown_count: int
    open_job_count: int
    active_release_count: int
