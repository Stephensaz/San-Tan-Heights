from dataclasses import fields
from dataclasses import replace
import pytest
from src.community_temporal_state.unified_seller_intelligence import *
from src.community_temporal_state.state_delta import *
from src.community_temporal_state.intelligence_usability import *

AREG="registries/community_temporal_state/m13-007a-unified-intelligence-v1.0.yaml"
EREG="registries/community_temporal_state/m13-007e-state-delta-v1.0.yaml"
FREG="registries/community_temporal_state/m13-007f-usability-v1.0.yaml"
def areg(): return load_unified_intelligence_registry(AREG)
def ereg(): return load_state_delta_registry(EREG)
def freg(): return load_usability_registry(FREG)
def ref(seed="a"): return make_source_ref(source_class="CERTIFIED_FACT",source_artifact_id="SRC",source_fingerprint=seed*64,source_time="2026-09-19T09:00:00-07:00",registry=areg())
def item(dim,value,seed="a",fresh="CURRENT",conflict="NO_CONFLICT",limitation=None):
    return make_intelligence_item(item_id="I-"+dim,dimension=dim,value=value,source_class="CERTIFIED_FACT",
      freshness_state=fresh,conflict_state=conflict,change_state="STALE" if fresh=="STALE" else "UNCHANGED",
      significance_class="REVIEW_REQUIRED" if conflict=="UNRESOLVED_CONFLICT" else "INFORMATIONAL",
      evidence_refs=(ref(seed),),registry=areg(),limitation=limitation)
def state(sid,time,items=(),unknowns=(),stale=(),limitations=()):
    return build_unified_state(intelligence_state_id=sid,property_id="P1",community_id="SAN-TAN-HEIGHTS",temporal_boundary=time,
      items=items,unknowns=unknowns,limitations=limitations,stale_dependencies=stale,policy_version="D-v1",schema_version="1.0.0",prior_state_fingerprint=None)
def rules(p,c):
    pitems={x.dimension:x for x in p.items}; citems={x.dimension:x for x in c.items}
    dims=sorted(set(pitems)|set(citems)|set(p.unknowns)|set(c.unknowns)); out=[]
    for i,d in enumerate(dims):
        pi=pitems.get(d); ci=citems.get(d)
        if d in c.unknowns: ch,sig="UNKNOWN","INSUFFICIENT_INFORMATION"
        elif d in p.unknowns and ci is not None: ch,sig="RESOLVED","INFORMATIONAL"
        elif pi is None and ci is not None: ch,sig="NEW","NOTICEABLE_CHANGE"
        elif pi is not None and ci is None: ch,sig="NO_LONGER_APPLICABLE","NOTICEABLE_CHANGE"
        elif ci and ci.freshness_state=="STALE": ch,sig="STALE","REVIEW_REQUIRED"
        elif pi.item_fingerprint==ci.item_fingerprint: ch,sig="UNCHANGED","INFORMATIONAL"
        else: ch,sig="CHANGED","MATERIAL_CHANGE"
        out.append(make_significance_rule(rule_id=f"R{i}",dimension=d,change_state=ch,significance_class=sig,reason="Governed rule.",registry=ereg()))
    return tuple(out)
def framework(p,c):
    l=build_change_ledger(ledger_id="L1",prior_state=p,current_state=c,significance_rules=rules(p,c),registry=ereg(),policy_version="E-v1")
    return assess_intelligence_usability(framework_id="F1",current_state=c,change_ledger=l,registry=freg(),policy_version="F-v1")

def test_usable_dimension():
    x=item("buyer_depth",3); p=state("P","2026-09-18T10:00:00-07:00",(x,)); c=state("C","2026-09-19T10:00:00-07:00",(x,))
    assert framework(p,c).assessments[0].usability_state=="USABLE"
def test_unresolved_conflict_blocks_only_affected_dimension():
    p=state("P","2026-09-18T10:00:00-07:00",(item("buyer_depth",2),item("scarcity",1,"b")))
    c=state("C","2026-09-19T10:00:00-07:00",(item("buyer_depth",3,"c",conflict="UNRESOLVED_CONFLICT"),item("scarcity",1,"b")))
    f=framework(p,c); m={x.dimension:x.usability_state for x in f.assessments}
    assert m["buyer_depth"]=="BLOCKED" and m["scarcity"]=="USABLE" and f.framework_status=="PARTIALLY_BLOCKED"
def test_stale_requires_review():
    p=state("P","2026-09-18T10:00:00-07:00",(item("buyer_depth",2),)); c=state("C","2026-09-19T10:00:00-07:00",(item("buyer_depth",2,"b",fresh="STALE"),))
    assert framework(p,c).assessments[0].usability_state=="REVIEW_REQUIRED"
def test_unknown_stays_unknown():
    p=state("P","2026-09-18T10:00:00-07:00"); c=state("C","2026-09-19T10:00:00-07:00",unknowns=("buyer_depth",))
    assert framework(p,c).assessments[0].usability_state=="UNKNOWN"
def test_limitation_is_preserved():
    p=state("P","2026-09-18T10:00:00-07:00",(item("buyer_depth",2),))
    c=state("C","2026-09-19T10:00:00-07:00",(item("buyer_depth",3,"b",limitation="Small sample."),))
    a=framework(p,c).assessments[0]; assert a.usability_state=="USABLE_WITH_LIMITATION" and "Small sample." in a.limitations
def test_stale_dependency_marks_framework_review_required_without_blocking_dimension():
    x=item("buyer_depth",3); p=state("P","2026-09-18T10:00:00-07:00",(x,)); c=state("C","2026-09-19T10:00:00-07:00",(x,),stale=("M13_TEMPORAL_STATE",))
    f=framework(p,c); assert f.framework_status=="REVIEW_REQUIRED" and f.assessments[0].usability_state=="USABLE"
def test_ledger_state_mismatch_rejected():
    x=item("buyer_depth",3); p=state("P","2026-09-18T10:00:00-07:00",(x,)); c=state("C","2026-09-19T10:00:00-07:00",(x,))
    l=build_change_ledger(ledger_id="L1",prior_state=p,current_state=c,significance_rules=rules(p,c),registry=ereg(),policy_version="E-v1")
    bad=replace(l,current_state_fingerprint="0"*64)
    with pytest.raises(ValueError,match="fingerprint mismatch"): assess_intelligence_usability(framework_id="F1",current_state=c,change_ledger=bad,registry=freg(),policy_version="F-v1")
def test_dimension_coverage_must_match():
    p=state("P","2026-09-18T10:00:00-07:00"); c=state("C","2026-09-19T10:00:00-07:00",unknowns=("buyer_depth",))
    l=build_change_ledger(ledger_id="L1",prior_state=p,current_state=c,significance_rules=rules(p,c),registry=ereg(),policy_version="E-v1")
    bad=replace(l,deltas=())
    with pytest.raises(ValueError,match="exactly match"): assess_intelligence_usability(framework_id="F1",current_state=c,change_ledger=bad,registry=freg(),policy_version="F-v1")
def test_deterministic_replay():
    x=item("buyer_depth",3); p=state("P","2026-09-18T10:00:00-07:00",(x,)); c=state("C","2026-09-19T10:00:00-07:00",(x,))
    l=build_change_ledger(ledger_id="L1",prior_state=p,current_state=c,significance_rules=rules(p,c),registry=ereg(),policy_version="E-v1")
    f=assess_intelligence_usability(framework_id="F1",current_state=c,change_ledger=l,registry=freg(),policy_version="F-v1")
    assert validate_usability_replay(f,framework_id="F1",current_state=c,change_ledger=l,registry=freg(),policy_version="F-v1")
def test_no_brief_recommendation_action_prediction_ranking_or_score_fields():
    forbidden={"brief","recommended_action","action","prediction","rank","seller_score","utility_score","execution_state"}
    for cls in (DimensionUsability,IntelligenceUsabilityFramework):
        assert {f.name for f in fields(cls)}.isdisjoint(forbidden)
