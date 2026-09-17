from pathlib import Path
from src.snapshot.requirements import load_snapshot_requirement_registry, SnapshotRequirementEngine
from tests.unit.snapshot._fixtures import state, finding, dep
ROOT=Path(__file__).resolve().parents[3]

def engine(): return SnapshotRequirementEngine(load_snapshot_requirement_registry(ROOT))

def test_complete_when_required_and_optional_present():
    s=state(findings=(finding('rear','REAR_ADJACENCY'),finding('corner','CORNER_STATUS'),finding('cul','CUL_DE_SAC_STATUS'),finding('view','VIEW_CLASSIFICATION')), dependencies=(dep('PROPERTY_IDENTITY','pid'),dep('PARCEL_IDENTITY','parcel')) )
    e=engine().evaluate(s)
    assert e.completeness_status=='COMPLETE'
    assert all(r.status=='SATISFIED' for r in e.results)

def test_optional_missing_is_partial_valid():
    s=state(dependencies=(dep('PROPERTY_IDENTITY','pid'),dep('PARCEL_IDENTITY','parcel')) )
    e=engine().evaluate(s)
    assert e.completeness_status=='PARTIAL_VALID'
    assert any(r.status=='OPTIONAL_MISSING' for r in e.results)

def test_missing_required_dependency_blocks():
    s=state(dependencies=(dep('PROPERTY_IDENTITY','pid'),))
    e=engine().evaluate(s)
    assert e.completeness_status=='BLOCKED'
    r=next(x for x in e.results if x.requirement_id=='REQ_PARCEL_IDENTITY_DEPENDENCY')
    assert r.status=='BLOCKED' and r.reason_code=='PARCEL_IDENTITY_DEPENDENCY_MISSING'

def test_invalid_upstream_state_is_invalid_not_blocked():
    e=engine().evaluate(state(identity='INVALID'))
    assert e.completeness_status=='INVALID'
