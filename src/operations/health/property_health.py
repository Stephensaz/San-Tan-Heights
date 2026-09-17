from __future__ import annotations
from uuid import UUID
from .models import HealthSignal, PropertyHealth, worst_status

class PropertyHealthModel:
    """Deterministically derives property health from governed operational signals."""
    def evaluate(self, *, property_id: UUID, has_current_snapshot: bool,
                 pointer_violations: int=0, orphan_count: int=0,
                 stuck_job_count: int=0, release_integrity_failures: int=0) -> PropertyHealth:
        signals=[]
        signals.append(HealthSignal('CURRENT_SNAPSHOT','HEALTHY' if has_current_snapshot else 'CRITICAL',0 if has_current_snapshot else 1))
        for code,count,level in (
            ('PUBLICATION_POINTER_INTEGRITY',pointer_violations,'CRITICAL'),
            ('ORPHANED_ARTIFACTS',orphan_count,'DEGRADED'),
            ('STUCK_JOBS',stuck_job_count,'DEGRADED'),
            ('RELEASE_INTEGRITY',release_integrity_failures,'CRITICAL')):
            signals.append(HealthSignal(code, level if count else 'HEALTHY', count))
        return PropertyHealth(property_id, worst_status(s.status for s in signals), tuple(signals))
