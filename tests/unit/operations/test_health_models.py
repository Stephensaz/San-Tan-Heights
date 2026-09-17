from uuid import uuid4
from src.operations.health.property_health import PropertyHealthModel
from src.operations.health.fleet_health import FleetHealthModel

def test_property_health_critical_on_pointer_or_release_failure():
    p=PropertyHealthModel().evaluate(property_id=uuid4(),has_current_snapshot=True,pointer_violations=1)
    assert p.status=='CRITICAL'
    assert next(s for s in p.signals if s.code=='PUBLICATION_POINTER_INTEGRITY').count==1

def test_property_health_degraded_for_stuck_jobs_only():
    p=PropertyHealthModel().evaluate(property_id=uuid4(),has_current_snapshot=True,stuck_job_count=2)
    assert p.status=='DEGRADED'

def test_fleet_health_aggregates_worst_and_signal_counts():
    m=PropertyHealthModel(); a=m.evaluate(property_id=uuid4(),has_current_snapshot=True); b=m.evaluate(property_id=uuid4(),has_current_snapshot=True,orphan_count=2)
    f=FleetHealthModel().aggregate([a,b])
    assert f.status=='DEGRADED' and f.total_properties==2 and f.signal_counts['ORPHANED_ARTIFACTS']==2
