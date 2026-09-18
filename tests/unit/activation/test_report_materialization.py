import json, hashlib, yaml, pytest
from src.activation import validate_report_materialization

def rec(pid,tier,keys,health="READY_WITH_LIMITATIONS",passport="a"*64,state=None):
    state = state or hashlib.sha256(f"{pid}|{tier}".encode()).hexdigest()
    r={"canonical_property_id":pid,"county_parcelid":pid.replace("STH-",""),"output_tier":tier,
       "passport_fingerprint":passport,"report_state_key":state,"template_version":"T1","labels_version":"L1",
       "glossary_version":"G1","branding_version":"B1","layout_version":"Y1","health_status":health,
       "displayed_finding_count":len(keys),"suppressed_finding_count":0,"displayed_finding_keys":keys,
       "stale_current_competition_displayed":False,"new_analytical_intelligence_created":False,
       "publication_state":"MATERIALIZED_NOT_PUBLISHED"}
    canon=json.dumps(r,sort_keys=True,separators=(",",":"),ensure_ascii=False)
    r["report_materialization_fingerprint"]=hashlib.sha256(canon.encode()).hexdigest()
    return r

def fixture(tmp_path):
    rs=[]
    for pid,health,passport in [("STH-1","READY_WITH_LIMITATIONS","a"*64),("STH-516018120","PARTIAL","b"*64)]:
        if pid=="STH-1":
            ks={"AGENT":["identity.community_membership","micro_market.membership"],"SELLER":["identity.community_membership"],"PUBLIC":["identity.community_membership"]}
        else:
            ks={t:["identity.community_membership"] for t in ("AGENT","SELLER","PUBLIC")}
        for t in ("AGENT","SELLER","PUBLIC"): rs.append(rec(pid,t,ks[t],health,passport))
    p=tmp_path/"reports.jsonl"; p.write_text("\n".join(json.dumps(r,sort_keys=True,separators=(",",":")) for r in rs)+"\n")
    agg=hashlib.sha256(("\n".join(r["report_materialization_fingerprint"] for r in rs)+"\n").encode()).hexdigest()
    reg={"report_materialization_registry_id":"STH-M9-007-AGENT-SELLER-PUBLIC-REPORTS-v1.0","version":"1.0.0","status":"FROZEN",
         "artifact":{"raw_sha256":hashlib.sha256(p.read_bytes()).hexdigest(),"aggregate_report_materialization_fingerprint":agg},
         "population":{"total_variants":6,"properties":2,"agent_variants":2,"seller_variants":2,"public_variants":2,"unique_report_state_keys":6},
         "displayed_findings":{"agent_total":3,"seller_total":2,"public_total":2},
         "tier_isolation":{"monotonicity_violations":0},
         "partial_property":{"canonical_property_id":"STH-516018120"},
         "publication_state":{"physical_delivery_activated":False,"public_delivery_activated":False},
         "governance":{k:True for k in ["only_tier_eligible_findings_displayed","stale_current_competition_suppressed","agent_only_not_in_seller_or_public","seller_only_not_in_public","limitations_and_health_preserved","passport_fingerprint_preserved","report_state_key_preserved","presentation_layer_recomputation_prohibited","new_intelligence_prohibited","raw_source_lookup_from_renderer_prohibited","publication_prohibited_in_m9_007"]}}
    rp=tmp_path/"reg.yaml"; rp.write_text(yaml.safe_dump(reg,sort_keys=False)); return rp,p,rs

def test_valid(tmp_path):
    r,p,_=fixture(tmp_path); a=validate_report_materialization(r,p); assert (a.records,a.properties)==(6,2)

def test_tier_leak_fails(tmp_path):
    r,p,rs=fixture(tmp_path); rs[4]["displayed_finding_keys"].append("agent.only"); rs[4]["displayed_finding_count"]+=1
    canon=dict(rs[4]); canon.pop("report_materialization_fingerprint"); rs[4]["report_materialization_fingerprint"]=hashlib.sha256(json.dumps(canon,sort_keys=True,separators=(",",":")).encode()).hexdigest()
    p.write_text("\n".join(json.dumps(x,sort_keys=True,separators=(",",":")) for x in rs)+"\n")
    with pytest.raises(ValueError,match="monotonicity"): validate_report_materialization(r,p)

def test_stale_current_fails(tmp_path):
    r,p,rs=fixture(tmp_path); rs[0]["stale_current_competition_displayed"]=True
    canon=dict(rs[0]); canon.pop("report_materialization_fingerprint"); rs[0]["report_materialization_fingerprint"]=hashlib.sha256(json.dumps(canon,sort_keys=True,separators=(",",":")).encode()).hexdigest()
    p.write_text("\n".join(json.dumps(x,sort_keys=True,separators=(",",":")) for x in rs)+"\n")
    with pytest.raises(ValueError,match="stale current competition"): validate_report_materialization(r,p)

def test_publication_activation_fails(tmp_path):
    r,p,_=fixture(tmp_path); raw=yaml.safe_load(r.read_text()); raw["publication_state"]["public_delivery_activated"]=True; r.write_text(yaml.safe_dump(raw,sort_keys=False))
    with pytest.raises(ValueError,match="public delivery activated"): validate_report_materialization(r,p)
