from dataclasses import fields,replace
import pytest
from src.community_temporal_state.cross_system_binding import *
from src.community_temporal_state.seller_relevance import *
from src.community_temporal_state.unified_seller_intelligence import load_unified_intelligence_registry
from src.community_temporal_state.current_unified_state import *

AREG="registries/community_temporal_state/m13-007a-unified-intelligence-v1.0.yaml"
BREG="registries/community_temporal_state/m13-007b-cross-system-binding-v1.0.yaml"
CREG="registries/community_temporal_state/m13-007c-applicability-v1.0.yaml"
DREG="registries/community_temporal_state/m13-007d-current-state-v1.0.yaml"
def areg(): return load_unified_intelligence_registry(AREG)
def breg(): return load_cross_system_binding_registry(BREG)
def creg(): return load_seller_relevance_registry(CREG)
def dreg(): return load_current_state_registry(DREG)

def bundle():
    deps=tuple(make_dependency(system_id=s,artifact_id=s+"-1",property_id="P1",community_id="SAN-TAN-HEIGHTS",
      as_of="2026-09-19T09:00:00-07:00",artifact_fingerprint=chr(97+i)*64,status="BOUND",registry=breg())
      for i,s in enumerate(breg()["required_systems"]))
    return resolve_input_bundle(bundle_id="B1",property_id="P1",community_id="SAN-TAN-HEIGHTS",
      temporal_boundary="2026-09-19T10:00:00-07:00",dependencies=deps,policy_version="B-v1",registry=breg())

def aset(b=None,states=(("buyer_depth","APPLICABLE"),("builder_competition","NOT_APPLICABLE"),("scarcity","UNKNOWN"))):
    b=b or bundle()
    ds=[]
    for i,(dim,state) in enumerate(states):
        rule=make_rule(rule_id=f"R{i}",dimension=dim,required_systems=("M13_TEMPORAL_STATE",))
        d=evaluate_applicability(decision_id=f"D{i}",bundle=b,rule=rule,
          property_facts={} if state=="UNKNOWN" else {},
          registry=creg())
        if state=="APPLICABLE":
            d=replace(d,applicability_state="APPLICABLE",rule_outcome="MATCH",reason="Property satisfies the governed applicability rule.",unknowns=())
        elif state=="NOT_APPLICABLE":
            d=replace(d,applicability_state="NOT_APPLICABLE",rule_outcome="NO_MATCH",reason="Property does not satisfy the governed applicability rule.",unknowns=(),exclusions=("governed_exclusion",))
        ds.append(d)
    return build_applicability_set(applicability_set_id="AS1",bundle=b,decisions=tuple(ds))

def cand(dim="buyer_depth",cid="I1"):
    return IntelligenceCandidate(candidate_id=cid,dimension=dim,value=3,source_class="CERTIFIED_FACT",
      source_artifact_id="SRC-1",source_fingerprint="f"*64,source_time="2026-09-19T09:00:00-07:00",
      freshness_state="CURRENT",conflict_state="NO_CONFLICT",limitation="Descriptive intelligence only.")

def build(b=None,a=None,candidates=None):
    b=b or bundle(); a=a or aset(b)
    return build_current_unified_state(intelligence_state_id="S1",bundle=b,applicability_set=a,
      candidates=(cand(),) if candidates is None else candidates,a_registry=areg(),d_registry=dreg(),
      policy_version="D-v1",schema_version="1.0.0")

def test_only_applicable_intelligence_is_materialized():
    r=build(); assert [x.dimension for x in r.state.items]==["buyer_depth"]; assert "builder_competition" in r.excluded_dimensions
def test_unknown_is_preserved_not_inferred():
    r=build(); assert "scarcity" in r.state.unknowns and all(x.dimension!="scarcity" for x in r.state.items)
def test_current_state_has_no_prior_state_fingerprint():
    assert build().state.prior_state_fingerprint is None
def test_applicability_bundle_mismatch_rejected():
    a=aset(); bad=replace(a,input_bundle_fingerprint="0"*64)
    with pytest.raises(ValueError,match="fingerprint mismatch"): build(a=bad)
def test_property_mismatch_rejected():
    a=replace(aset(),subject_property_id="P2")
    with pytest.raises(ValueError,match="property mismatch"): build(a=a)
def test_temporal_mismatch_rejected():
    a=replace(aset(),temporal_boundary="2026-09-18T10:00:00-07:00")
    with pytest.raises(ValueError,match="temporal boundary mismatch"): build(a=a)
def test_blocked_applicability_fails_closed():
    a=aset(states=(("buyer_depth","APPLICABLE"),))
    d=replace(a.decisions[0],applicability_state="BLOCKED",rule_outcome="BLOCKED_DEPENDENCY")
    a=replace(a,decisions=(d,))
    with pytest.raises(ValueError,match="blocked applicability"): build(a=a)
def test_applicable_dimension_requires_exactly_one_candidate():
    a=aset(states=(("buyer_depth","APPLICABLE"),))
    with pytest.raises(ValueError,match="exactly one"): build(a=a,candidates=())
def test_candidate_without_decision_is_rejected():
    with pytest.raises(ValueError,match="without governed applicability"): build(candidates=(cand(),cand("extra","I2")))
def test_deterministic_replay():
    r=build()
    assert validate_current_state_result_replay(r,intelligence_state_id="S1",bundle=bundle(),applicability_set=aset(bundle()),
      candidates=(cand(),),a_registry=areg(),d_registry=dreg(),policy_version="D-v1",schema_version="1.0.0")
def test_no_delta_recommendation_prediction_or_execution_fields():
    forbidden={"prior_delta","material_change","recommended_action","recommended_price","prediction","rank","seller_score","execution_state"}
    for cls in (IntelligenceCandidate,CurrentStateBuildResult):
        assert {f.name for f in fields(cls)}.isdisjoint(forbidden)
