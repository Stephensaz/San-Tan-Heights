from dataclasses import fields,replace
import pytest
from src.community_temporal_state.unified_seller_intelligence import *
from src.community_temporal_state.current_unified_state import CurrentStateBuildResult
from src.community_temporal_state.state_delta import *
from src.community_temporal_state.intelligence_usability import *
from src.community_temporal_state.seller_decision_brief import *

AREG="registries/community_temporal_state/m13-007a-unified-intelligence-v1.0.yaml"
EREG="registries/community_temporal_state/m13-007e-state-delta-v1.0.yaml"
FREG="registries/community_temporal_state/m13-007f-usability-v1.0.yaml"
GREG="registries/community_temporal_state/m13-007g-seller-brief-v1.0.yaml"
def areg(): return load_unified_intelligence_registry(AREG)
def ereg(): return load_state_delta_registry(EREG)
def freg(): return load_usability_registry(FREG)
def greg(): return load_seller_brief_registry(GREG)
def ref(seed="a"): return make_source_ref(source_class="CERTIFIED_FACT",source_artifact_id="SRC",source_fingerprint=seed*64,source_time="2026-09-19T09:00:00-07:00",registry=areg())
def item(dim,value,seed="a",fresh="CURRENT",conflict="NO_CONFLICT",limitation=None):
    return make_intelligence_item(item_id="I-"+dim,dimension=dim,value=value,source_class="CERTIFIED_FACT",
      freshness_state=fresh,conflict_state=conflict,change_state="STALE" if fresh=="STALE" else "UNCHANGED",
      significance_class="REVIEW_REQUIRED" if conflict=="UNRESOLVED_CONFLICT" else "INFORMATIONAL",
      evidence_refs=(ref(seed),),registry=areg(),limitation=limitation)
def state(sid,time,items=(),unknowns=(),limitations=()):
    return build_unified_state(intelligence_state_id=sid,property_id="P1",community_id="SAN-TAN-HEIGHTS",temporal_boundary=time,
      items=items,unknowns=unknowns,limitations=limitations,stale_dependencies=(),policy_version="D-v1",schema_version="1.0.0",prior_state_fingerprint=None)
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
def inputs():
    p=state("P","2026-09-18T10:00:00-07:00",(item("buyer_depth",2),))
    c=state("C","2026-09-19T10:00:00-07:00",(item("buyer_depth",3,"b",limitation="Descriptive only."),),unknowns=("scarcity",),limitations=("Global limitation.",))
    cr=CurrentStateBuildResult(state=c,applicability_set_fingerprint="a"*64,input_bundle_fingerprint="b"*64,excluded_dimensions=("builder_competition",),unknown_dimensions=("scarcity",),result_fingerprint="c"*64)
    ledger=build_change_ledger(ledger_id="L1",prior_state=p,current_state=c,significance_rules=rules(p,c),registry=ereg(),policy_version="E-v1")
    usage=assess_intelligence_usability(framework_id="F1",current_state=c,change_ledger=ledger,registry=freg(),policy_version="F-v1")
    return cr,ledger,usage
def brief(cr=None,l=None,u=None):
    a,b,c=inputs()
    return assemble_seller_decision_brief(brief_id="G1",current_result=cr or a,change_ledger=l or b,usability=u or c,registry=greg(),policy_version="G-v1")

def test_brief_preserves_current_change_usability():
    b=brief(); row={x.dimension:x for x in b.dimensions}["buyer_depth"]
    assert row.current_value==3 and row.change_state=="CHANGED" and row.usability_state=="USABLE_WITH_LIMITATION"
def test_unknowns_exclusions_and_limitations_preserved():
    b=brief(); assert "scarcity" in b.unknowns and "builder_competition" in b.exclusions and "Global limitation." in b.limitations
def test_unknown_dimension_has_no_invented_value_or_evidence():
    row={x.dimension:x for x in brief().dimensions}["scarcity"]; assert row.current_value is None and row.evidence_source_fingerprints==()
def test_review_conditions_are_explicit():
    b=brief(); assert set(b.review_required_dimensions)=={"buyer_depth","scarcity"}
def test_exact_state_match_required():
    cr,l,u=inputs(); bad=replace(l,current_state_fingerprint="0"*64)
    with pytest.raises(ValueError,match="fingerprint mismatch"): brief(cr,bad,u)
def test_exact_usability_ledger_match_required():
    cr,l,u=inputs(); bad=replace(u,change_ledger_fingerprint="0"*64)
    with pytest.raises(ValueError,match="change ledger fingerprint mismatch"): brief(cr,l,bad)
def test_blocked_dimension_never_presented_as_usable():
    cr,l,u=inputs(); a=list(u.assessments); a[0]=replace(a[0],usability_state="BLOCKED",reasons=("Unresolved evidence conflict blocks this dimension.",)); u=replace(u,assessments=tuple(a))
    b=brief(cr,l,u); assert "buyer_depth" in b.blocked_dimensions and {x.dimension:x for x in b.dimensions}["buyer_depth"].usability_state=="BLOCKED"
def test_dimension_coverage_must_match():
    cr,l,u=inputs(); bad=replace(u,assessments=u.assessments[:-1])
    with pytest.raises(ValueError,match="coverage mismatch"): brief(cr,l,bad)
def test_deterministic_replay():
    cr,l,u=inputs(); b=brief(cr,l,u)
    assert validate_seller_brief_replay(b,brief_id="G1",current_result=cr,change_ledger=l,usability=u,registry=greg(),policy_version="G-v1")
def test_no_analysis_recommendation_price_action_prediction_ranking_or_score_fields():
    forbidden={"analysis","recommendation","recommended_action","recommended_price","list_price","pricing_strategy","action","prediction","rank","seller_score","utility_score","execution_state"}
    for cls in (SellerBriefDimension,GovernedSellerDecisionBrief):
        assert {f.name for f in fields(cls)}.isdisjoint(forbidden)
