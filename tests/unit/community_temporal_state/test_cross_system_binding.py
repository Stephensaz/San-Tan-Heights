from dataclasses import fields
import pytest
from src.community_temporal_state.cross_system_binding import *

REG="registries/community_temporal_state/m13-007b-cross-system-binding-v1.0.yaml"
def reg(): return load_cross_system_binding_registry(REG)
def dep(system,status="BOUND",prop="P1",community="SAN-TAN-HEIGHTS",as_of="2026-09-19T09:00:00-07:00",seed="a"):
    return make_dependency(system_id=system,artifact_id=system+"-1",property_id=prop,community_id=community,as_of=as_of,artifact_fingerprint=seed*64,status=status,registry=reg())
def all_deps():
    return tuple(dep(s,seed=chr(97+i)) for i,s in enumerate(reg()["required_systems"]))
def bundle(deps=None):
    return resolve_input_bundle(bundle_id="B1",property_id="P1",community_id="SAN-TAN-HEIGHTS",temporal_boundary="2026-09-19T10:00:00-07:00",dependencies=all_deps() if deps is None else deps,policy_version="M13-007B-v1",registry=reg())

def test_required_systems_are_frozen():
    assert set(reg()["required_systems"])=={"M11_SELLER_INTELLIGENCE","M13_TEMPORAL_STATE","M13_TEMPORAL_DELTA","M13_TEMPORAL_HISTORY","M13_PROMOTED_PATTERNS","M13_SCENARIO_INTELLIGENCE"}
def test_exact_property_binding():
    ds=list(all_deps()); ds[0]=dep(ds[0].system_id,prop="P2")
    with pytest.raises(ValueError,match="property identity"): bundle(tuple(ds))
def test_exact_community_binding():
    ds=list(all_deps()); ds[0]=dep(ds[0].system_id,community="OTHER")
    with pytest.raises(ValueError,match="community identity"): bundle(tuple(ds))
def test_future_dependency_rejected():
    ds=list(all_deps()); ds[0]=dep(ds[0].system_id,as_of="2026-09-20T10:00:00-07:00")
    with pytest.raises(ValueError,match="future"): bundle(tuple(ds))
def test_missing_dependency_is_explicit():
    b=bundle(all_deps()[:-1]); assert b.bundle_status=="INCOMPLETE" and b.missing_systems
def test_stale_dependency_is_explicit():
    ds=list(all_deps()); ds[0]=dep(ds[0].system_id,status="STALE")
    b=bundle(tuple(ds)); assert b.bundle_status=="INCOMPLETE" and b.stale_systems==(ds[0].system_id,)
def test_conflicting_dependency_blocks():
    ds=list(all_deps()); ds[0]=dep(ds[0].system_id,status="CONFLICTING")
    b=bundle(tuple(ds)); assert b.bundle_status=="BLOCKED" and b.conflicting_systems
def test_incompatible_dependency_blocks():
    ds=list(all_deps()); ds[0]=dep(ds[0].system_id,status="INCOMPATIBLE")
    b=bundle(tuple(ds)); assert b.bundle_status=="BLOCKED" and b.incompatible_systems
def test_duplicate_system_rejected():
    d=all_deps()[0]
    with pytest.raises(ValueError,match="duplicate"): bundle((d,d))
def test_bad_fingerprint_rejected():
    with pytest.raises(ValueError,match="sha256"): make_dependency(system_id="M11_SELLER_INTELLIGENCE",artifact_id="A",property_id="P1",community_id="SAN-TAN-HEIGHTS",as_of="2026-09-19T09:00:00-07:00",artifact_fingerprint="bad",status="BOUND",registry=reg())
def test_deterministic_ordering_and_replay():
    ds=all_deps(); a=bundle(ds); b=bundle(tuple(reversed(ds))); assert a.bundle_fingerprint==b.bundle_fingerprint
    assert validate_input_bundle_replay(a,bundle_id="B1",property_id="P1",community_id="SAN-TAN-HEIGHTS",temporal_boundary="2026-09-19T10:00:00-07:00",dependencies=ds,policy_version="M13-007B-v1",registry=reg())
def test_no_relevance_synthesis_or_decision_fields():
    forbidden={"relevance_score","applicable","unified_state","recommended_action","recommended_price","rank","winner","seller_score","execution_state"}
    for cls in (DependencyArtifact,GovernedInputBundle):
        assert {f.name for f in fields(cls)}.isdisjoint(forbidden)
