from dataclasses import fields, replace
import pytest
from src.community_temporal_state.scenario_explainability import ScenarioExplanation, ComparisonExplanation
from src.community_temporal_state.scenario_review_workspace import *

REG="registries/community_temporal_state/m13-006i-review-workspace-v1.0.yaml"
def reg(): return load_review_workspace_registry(REG)
def sx(sid,seed):
    return ScenarioExplanation(scenario_id=sid,scenario_context_fingerprint="a"*64,comparison_member_fingerprint="b"*64,
      facts=(("bedrooms",4),),assumptions=(("candidate_price",500000+seed),),modeled_dimensions=("pricing_position",),
      changed_from_reference=("pricing_position",),evidence_source_fingerprints=("c"*64,),evidence_fingerprints=((("d" if seed==1 else "e")*64),),
      applicable_pattern_ids=("P1",),unknown_pattern_ids=(),unknowns=("buyer_depth_unknown",),limitations=("Historical only.",),
      explanation_fingerprint=(("1" if seed==1 else "2")*64))
def cx():
    return ComparisonExplanation(comparison_id="C1",comparison_fingerprint="f"*64,scenario_ids=("S1","S2"),
      scenario_explanation_fingerprints=("1"*64,"2"*64),pairwise_differences=(("S1","S2","pricing_position",1,2,"LEFT_LOWER"),),
      unknowns=("buyer_depth_unknown",),limitations=("No preference implied.",),explanation_fingerprint="9"*64)
def pkg(**kw):
    args=dict(review_package_id="R1",subject_id="P1",community_id="SAN-TAN-HEIGHTS",baseline_snapshot_id="B1",
      temporal_boundary="2026-09-19T00:00:00-07:00",scenario_explanations=(sx("S1",1),sx("S2",2)),comparison_explanation=cx(),
      policy_version="I-v1",registry=reg())
    args.update(kw); return build_review_package(**args)
def test_ready_package_is_deterministic(): assert pkg()==pkg()
def test_package_preserves_unknowns_and_limitations():
    p=pkg(); assert p.package_status=="READY_FOR_HUMAN_REVIEW"; assert p.unknowns and p.limitations
def test_missing_explanation_blocks_build():
    with pytest.raises(ValueError,match="coverage"): pkg(scenario_explanations=(sx("S1",1),))
def test_lineage_mismatch_blocks_build():
    bad=replace(cx(),scenario_explanation_fingerprints=("2"*64,"1"*64))
    with pytest.raises(ValueError,match="lineage"): pkg(comparison_explanation=bad)
def test_explicit_blocking_condition_marks_stale(): assert pkg(blocking_conditions=("STALE_BASELINE",)).package_status=="STALE_REVIEW_REQUIRED"
def test_mark_stale_creates_new_hash_without_mutating_original():
    p=pkg(); q=mark_package_stale(p,condition="HASH_MISMATCH",registry=reg()); assert p.package_status=="READY_FOR_HUMAN_REVIEW" and q.package_fingerprint!=p.package_fingerprint
def test_human_review_is_separate_receipt():
    p=pkg(); r=record_human_review(package=p,review_state="NO_DECISION_MADE",reviewer_id="human",registry=reg()); assert r.review_package_fingerprint==p.package_fingerprint
def test_stale_package_cannot_be_reviewed():
    with pytest.raises(ValueError,match="not ready"): record_human_review(package=pkg(blocking_conditions=("STALE_BASELINE",)),review_state="REVIEWED",reviewer_id="human",registry=reg())
def test_replay_is_exact():
    p=pkg(); assert validate_review_package_replay(p,review_package_id="R1",subject_id="P1",community_id="SAN-TAN-HEIGHTS",baseline_snapshot_id="B1",temporal_boundary="2026-09-19T00:00:00-07:00",scenario_explanations=(sx("S1",1),sx("S2",2)),comparison_explanation=cx(),policy_version="I-v1",registry=reg())
def test_no_decision_fields_exist():
    forbidden={"rank","winner","recommended_action","recommended_price","utility_score","prediction","execution_state"}
    assert set(x.name for x in fields(ScenarioReviewPackage)).isdisjoint(forbidden)
def test_unknown_blocking_code_rejected():
    with pytest.raises(ValueError,match="unsupported"): pkg(blocking_conditions=("INVENTED",))
def test_review_state_is_governed():
    with pytest.raises(ValueError,match="unsupported"): record_human_review(package=pkg(),review_state="APPROVE_BEST",reviewer_id="human",registry=reg())
