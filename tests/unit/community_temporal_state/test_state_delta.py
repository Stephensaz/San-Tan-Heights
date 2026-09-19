from dataclasses import fields,replace
import pytest
from src.community_temporal_state.unified_seller_intelligence import *
from src.community_temporal_state.state_delta import *

AREG="registries/community_temporal_state/m13-007a-unified-intelligence-v1.0.yaml"
EREG="registries/community_temporal_state/m13-007e-state-delta-v1.0.yaml"
def areg(): return load_unified_intelligence_registry(AREG)
def ereg(): return load_state_delta_registry(EREG)
def ref(seed="a"): return make_source_ref(source_class="CERTIFIED_FACT",source_artifact_id="SRC",source_fingerprint=seed*64,source_time="2026-09-19T09:00:00-07:00",registry=areg())
def item(dim,value,seed="a",fresh="CURRENT"):
    return make_intelligence_item(item_id="I-"+dim,dimension=dim,value=value,source_class="CERTIFIED_FACT",freshness_state=fresh,
      conflict_state="NO_CONFLICT",change_state="UNCHANGED" if fresh!="STALE" else "STALE",significance_class="INFORMATIONAL",
      evidence_refs=(ref(seed),),registry=areg())
def state(sid,time,items=(),unknowns=()):
    return build_unified_state(intelligence_state_id=sid,property_id="P1",community_id="SAN-TAN-HEIGHTS",temporal_boundary=time,
      items=items,unknowns=unknowns,limitations=(),stale_dependencies=(),policy_version="D-v1",schema_version="1.0.0",prior_state_fingerprint=None)
def rules(p,c):
    pitems={x.dimension:x for x in p.items}; citems={x.dimension:x for x in c.items}
    dims=sorted(set(pitems)|set(citems)|set(p.unknowns)|set(c.unknowns))
    out=[]
    for i,d in enumerate(dims):
        pi=pitems.get(d); ci=citems.get(d)
        if d in c.unknowns: ch="UNKNOWN"; sig="INSUFFICIENT_INFORMATION"
        elif d in p.unknowns and ci is not None: ch="RESOLVED"; sig="INFORMATIONAL"
        elif pi is None and ci is not None: ch="NEW"; sig="NOTICEABLE_CHANGE"
        elif pi is not None and ci is None: ch="NO_LONGER_APPLICABLE"; sig="NOTICEABLE_CHANGE"
        elif ci and ci.freshness_state=="STALE": ch="STALE"; sig="REVIEW_REQUIRED"
        elif pi.item_fingerprint==ci.item_fingerprint: ch="UNCHANGED"; sig="INFORMATIONAL"
        else: ch="CHANGED"; sig="MATERIAL_CHANGE"
        out.append(make_significance_rule(rule_id=f"R{i}",dimension=d,change_state=ch,significance_class=sig,reason="Explicit governed significance rule.",registry=ereg()))
    return tuple(out)

def ledger(p,c): return build_change_ledger(ledger_id="L1",prior_state=p,current_state=c,significance_rules=rules(p,c),registry=ereg(),policy_version="E-v1")

def test_new_change():
    p=state("P","2026-09-18T10:00:00-07:00"); c=state("C","2026-09-19T10:00:00-07:00",(item("buyer_depth",3),))
    assert ledger(p,c).deltas[0].change_state=="NEW"
def test_changed_and_material_rule():
    p=state("P","2026-09-18T10:00:00-07:00",(item("buyer_depth",2,"a"),)); c=state("C","2026-09-19T10:00:00-07:00",(item("buyer_depth",3,"b"),))
    d=ledger(p,c).deltas[0]; assert d.change_state=="CHANGED" and d.significance_class=="MATERIAL_CHANGE"
def test_unchanged():
    x=item("buyer_depth",3); p=state("P","2026-09-18T10:00:00-07:00",(x,)); c=state("C","2026-09-19T10:00:00-07:00",(x,))
    assert ledger(p,c).deltas[0].change_state=="UNCHANGED"
def test_stale():
    p=state("P","2026-09-18T10:00:00-07:00",(item("buyer_depth",2),)); c=state("C","2026-09-19T10:00:00-07:00",(item("buyer_depth",2,fresh="STALE"),))
    assert ledger(p,c).deltas[0].change_state=="STALE"
def test_resolved_unknown():
    p=state("P","2026-09-18T10:00:00-07:00",unknowns=("buyer_depth",)); c=state("C","2026-09-19T10:00:00-07:00",(item("buyer_depth",3),))
    assert ledger(p,c).deltas[0].change_state=="RESOLVED"
def test_no_longer_applicable():
    p=state("P","2026-09-18T10:00:00-07:00",(item("buyer_depth",3),)); c=state("C","2026-09-19T10:00:00-07:00")
    assert ledger(p,c).deltas[0].change_state=="NO_LONGER_APPLICABLE"
def test_unknown():
    p=state("P","2026-09-18T10:00:00-07:00"); c=state("C","2026-09-19T10:00:00-07:00",unknowns=("buyer_depth",))
    assert ledger(p,c).deltas[0].change_state=="UNKNOWN"
def test_property_mismatch_rejected():
    p=state("P","2026-09-18T10:00:00-07:00"); c=replace(state("C","2026-09-19T10:00:00-07:00"),property_id="P2")
    with pytest.raises(ValueError,match="property mismatch"): ledger(p,c)
def test_non_forward_time_rejected():
    p=state("P","2026-09-19T10:00:00-07:00"); c=state("C","2026-09-19T10:00:00-07:00")
    with pytest.raises(ValueError,match="must precede"): ledger(p,c)
def test_explicit_significance_rule_required():
    p=state("P","2026-09-18T10:00:00-07:00"); c=state("C","2026-09-19T10:00:00-07:00",(item("buyer_depth",3),))
    with pytest.raises(ValueError,match="explicit significance rule"): build_change_ledger(ledger_id="L1",prior_state=p,current_state=c,significance_rules=(),registry=ereg(),policy_version="E-v1")
def test_deterministic_replay():
    p=state("P","2026-09-18T10:00:00-07:00",(item("buyer_depth",2),)); c=state("C","2026-09-19T10:00:00-07:00",(item("buyer_depth",3,"b"),))
    x=ledger(p,c)
    assert validate_change_ledger_replay(x,ledger_id="L1",prior_state=p,current_state=c,significance_rules=rules(p,c),registry=ereg(),policy_version="E-v1")
def test_no_recommendation_action_prediction_ranking_or_score_fields():
    forbidden={"recommended_action","recommended_price","action","prediction","rank","seller_score","utility_score","execution_state"}
    for cls in (SignificanceRule,IntelligenceDelta,SellerIntelligenceChangeLedger):
        assert {f.name for f in fields(cls)}.isdisjoint(forbidden)
