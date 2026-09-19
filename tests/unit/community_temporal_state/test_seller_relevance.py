from dataclasses import fields, replace
import pytest
from src.community_temporal_state.cross_system_binding import make_dependency,resolve_input_bundle,load_cross_system_binding_registry
from src.community_temporal_state.seller_relevance import *

BREG="registries/community_temporal_state/m13-007b-cross-system-binding-v1.0.yaml"
CREG="registries/community_temporal_state/m13-007c-applicability-v1.0.yaml"
def breg(): return load_cross_system_binding_registry(BREG)
def creg(): return load_seller_relevance_registry(CREG)
def bundle():
    deps=tuple(make_dependency(system_id=s,artifact_id=s+"-1",property_id="P1",community_id="SAN-TAN-HEIGHTS",as_of="2026-09-19T09:00:00-07:00",artifact_fingerprint=chr(97+i)*64,status="BOUND",registry=breg()) for i,s in enumerate(breg()["required_systems"]))
    return resolve_input_bundle(bundle_id="B1",property_id="P1",community_id="SAN-TAN-HEIGHTS",temporal_boundary="2026-09-19T10:00:00-07:00",dependencies=deps,policy_version="B-v1",registry=breg())
def rule(**kw):
    args=dict(rule_id="R1",dimension="new_construction_competition",required_systems=("M13_SCENARIO_INTELLIGENCE",),required_property_facts=(("price_band","500-600"),))
    args.update(kw); return make_rule(**args)

def test_applicable_when_governed_rule_matches():
    d=evaluate_applicability(decision_id="D1",bundle=bundle(),rule=rule(),property_facts={"price_band":"500-600"},registry=creg())
    assert d.applicability_state=="APPLICABLE" and d.rule_outcome=="MATCH"
def test_not_applicable_preserves_exclusion_reason():
    d=evaluate_applicability(decision_id="D1",bundle=bundle(),rule=rule(),property_facts={"price_band":"600-700"},registry=creg())
    assert d.applicability_state=="NOT_APPLICABLE" and d.exclusions==("price_band",)
def test_unknown_preserved_for_missing_property_fact():
    d=evaluate_applicability(decision_id="D1",bundle=bundle(),rule=rule(),property_facts={},registry=creg())
    assert d.applicability_state=="UNKNOWN" and d.unknowns==("price_band",)
def test_non_ready_bundle_is_rejected():
    b=replace(bundle(),bundle_status="INCOMPLETE")
    with pytest.raises(ValueError,match="READY"): evaluate_applicability(decision_id="D1",bundle=b,rule=rule(),property_facts={"price_band":"500-600"},registry=creg())
def test_rule_and_decision_are_deterministic():
    r1=rule(required_systems=("M13_SCENARIO_INTELLIGENCE","M13_TEMPORAL_STATE")); r2=rule(required_systems=("M13_TEMPORAL_STATE","M13_SCENARIO_INTELLIGENCE"))
    assert r1.rule_fingerprint==r2.rule_fingerprint
    assert evaluate_applicability(decision_id="D1",bundle=bundle(),rule=r1,property_facts={"price_band":"500-600"},registry=creg())==evaluate_applicability(decision_id="D1",bundle=bundle(),rule=r2,property_facts={"price_band":"500-600"},registry=creg())
def test_dependency_lineage_is_preserved():
    d=evaluate_applicability(decision_id="D1",bundle=bundle(),rule=rule(),property_facts={"price_band":"500-600"},registry=creg())
    assert len(d.source_dependency_fingerprints)==1 and len(d.source_dependency_fingerprints[0])==64
def test_duplicate_decision_ids_rejected():
    d=evaluate_applicability(decision_id="D1",bundle=bundle(),rule=rule(),property_facts={"price_band":"500-600"},registry=creg())
    with pytest.raises(ValueError,match="duplicate"): build_applicability_set(applicability_set_id="S1",bundle=bundle(),decisions=(d,d))
def test_property_mismatch_rejected():
    d=evaluate_applicability(decision_id="D1",bundle=bundle(),rule=rule(),property_facts={"price_band":"500-600"},registry=creg())
    with pytest.raises(ValueError,match="property mismatch"): build_applicability_set(applicability_set_id="S1",bundle=bundle(),decisions=(replace(d,subject_property_id="P2"),))
def test_set_ordering_and_replay_are_deterministic():
    d1=evaluate_applicability(decision_id="D1",bundle=bundle(),rule=rule(),property_facts={"price_band":"500-600"},registry=creg())
    d2=evaluate_applicability(decision_id="D2",bundle=bundle(),rule=rule(rule_id="R2",dimension="buyer_depth"),property_facts={"price_band":"500-600"},registry=creg())
    s1=build_applicability_set(applicability_set_id="S1",bundle=bundle(),decisions=(d1,d2)); s2=build_applicability_set(applicability_set_id="S1",bundle=bundle(),decisions=(d2,d1))
    assert s1.set_fingerprint==s2.set_fingerprint
    assert validate_applicability_set_replay(s1,applicability_set_id="S1",bundle=bundle(),decisions=(d1,d2))
def test_no_scoring_recommendation_prediction_or_state_synthesis_fields():
    forbidden={"relevance_score","weight","recommended_action","recommended_price","prediction","rank","seller_score","unified_state","execution_state"}
    for cls in (ApplicabilityRule,ApplicabilityDecision,ApplicabilitySet):
        assert {f.name for f in fields(cls)}.isdisjoint(forbidden)
