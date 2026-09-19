from dataclasses import fields
import pytest
from src.community_temporal_state.unified_seller_intelligence import *

REG="registries/community_temporal_state/m13-007a-unified-intelligence-v1.0.yaml"
def reg(): return load_unified_intelligence_registry(REG)
def ref(cls="CERTIFIED_FACT",seed="a"):
    return make_source_ref(source_class=cls,source_artifact_id="SRC-1",source_fingerprint=seed*64,source_time="2026-09-19T00:00:00-07:00",registry=reg())
def item(**kw):
    args=dict(item_id="I1",dimension="buyer_depth",value=3,source_class="CERTIFIED_FACT",freshness_state="CURRENT",
      conflict_state="NO_CONFLICT",change_state="UNCHANGED",significance_class="INFORMATIONAL",evidence_refs=(ref(),),registry=reg())
    args.update(kw); return make_intelligence_item(**args)
def state(items=(None,),**kw):
    its=(item(),) if items==(None,) else items
    args=dict(intelligence_state_id="S1",property_id="P1",community_id="SAN-TAN-HEIGHTS",
      temporal_boundary="2026-09-19T00:00:00-07:00",items=its,unknowns=(),limitations=(),
      stale_dependencies=(),policy_version="M13-007A-v1",schema_version="1.0.0")
    args.update(kw); return build_unified_state(**args)

def test_registry_taxonomy_is_complete():
    r=reg()
    assert set(r["source_classes"])=={"CERTIFIED_FACT","CURRENT_OBSERVATION","HISTORICAL_OBSERVATION","PROMOTED_PATTERN","EXPLICIT_SCENARIO_ASSUMPTION","SCENARIO_RESULT","UNKNOWN","LIMITATION","HUMAN_INPUT"}
def test_source_ref_rejects_unknown_class():
    with pytest.raises(ValueError,match="unsupported source class"): ref("INFERRED_GUESS")
def test_material_item_requires_lineage():
    with pytest.raises(ValueError,match="evidence lineage"): item(evidence_refs=())
def test_unknown_cannot_be_inferred():
    with pytest.raises(ValueError,match="cannot carry inferred"): item(source_class="UNKNOWN",value=5,evidence_refs=())
def test_unknown_can_remain_unknown():
    x=item(source_class="UNKNOWN",value=None,evidence_refs=(),significance_class="INSUFFICIENT_INFORMATION"); assert x.value is None
def test_stale_state_is_explicit():
    with pytest.raises(ValueError,match="stale freshness"): item(freshness_state="STALE",change_state="UNCHANGED")
def test_unresolved_conflict_requires_review():
    with pytest.raises(ValueError,match="requires review"): item(conflict_state="UNRESOLVED_CONFLICT",significance_class="INFORMATIONAL")
def test_deterministic_item_ordering():
    a=item(item_id="A"); b=item(item_id="B",dimension="comparable_depth")
    assert state(items=(a,b)).state_fingerprint==state(items=(b,a)).state_fingerprint
def test_duplicate_item_ids_rejected():
    with pytest.raises(ValueError,match="duplicate"): state(items=(item(),item()))
def test_prior_state_fingerprint_must_be_valid():
    with pytest.raises(ValueError,match="sha256"): state(prior_state_fingerprint="bad")
def test_state_replay_is_exact():
    s=state()
    assert validate_unified_state_replay(s,intelligence_state_id="S1",property_id="P1",community_id="SAN-TAN-HEIGHTS",
      temporal_boundary="2026-09-19T00:00:00-07:00",items=(item(),),unknowns=(),limitations=(),stale_dependencies=(),
      policy_version="M13-007A-v1",schema_version="1.0.0")
def test_no_recommendation_prediction_ranking_or_execution_fields_exist():
    forbidden={"recommended_price","recommended_action","rank","winner","utility_score","seller_score","lead_score","prediction","sale_probability","execution_state"}
    for cls in (IntelligenceSourceRef,UnifiedIntelligenceItem,UnifiedSellerIntelligenceState):
        assert {f.name for f in fields(cls)}.isdisjoint(forbidden)
def test_significance_classes_are_descriptive_only():
    assert set(reg()["significance_classes"])=={"INFORMATIONAL","NOTICEABLE_CHANGE","MATERIAL_CHANGE","REVIEW_REQUIRED","INSUFFICIENT_INFORMATION"}
