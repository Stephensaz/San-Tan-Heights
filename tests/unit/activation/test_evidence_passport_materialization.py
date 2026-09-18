import csv
from pathlib import Path
import hashlib
import yaml
import pytest

from src.activation import validate_materialization


def write_csv(path, fieldnames, rows):
    with path.open("w", newline="", encoding="utf-8") as h:
        w=csv.DictWriter(h,fieldnames=fieldnames,lineterminator="\n"); w.writeheader(); w.writerows(rows)


def fixtures(tmp_path):
    summary=tmp_path/"summary.csv"
    write_csv(summary,["canonical_property_id","county_parcelid","health_status","finding_count","active_limitation_count","internal_eligible_finding_count","agent_eligible_finding_count","seller_eligible_finding_count","public_eligible_finding_count","internal_suppressed_finding_count","agent_suppressed_finding_count","seller_suppressed_finding_count","public_suppressed_finding_count","passport_fingerprint","passport_version","governance_version"],[
        {"canonical_property_id":"STH-1","county_parcelid":"1","health_status":"READY_WITH_LIMITATIONS","finding_count":"1","active_limitation_count":"0","internal_eligible_finding_count":"1","agent_eligible_finding_count":"1","seller_eligible_finding_count":"1","public_eligible_finding_count":"1","internal_suppressed_finding_count":"0","agent_suppressed_finding_count":"0","seller_suppressed_finding_count":"0","public_suppressed_finding_count":"0","passport_fingerprint":"a"*64,"passport_version":"PASSPORT_2","governance_version":"EVIDENCE_GOVERNANCE_2"},
        {"canonical_property_id":"STH-516018120","county_parcelid":"516018120","health_status":"PARTIAL","finding_count":"1","active_limitation_count":"1","internal_eligible_finding_count":"1","agent_eligible_finding_count":"0","seller_eligible_finding_count":"0","public_eligible_finding_count":"0","internal_suppressed_finding_count":"0","agent_suppressed_finding_count":"1","seller_suppressed_finding_count":"1","public_suppressed_finding_count":"1","passport_fingerprint":"b"*64,"passport_version":"PASSPORT_2","governance_version":"EVIDENCE_GOVERNANCE_2"},
    ])
    findings=tmp_path/"findings.csv"
    write_csv(findings,["canonical_property_id","county_parcelid","finding_key","finding_domain","finding_status","confidence_class","qa_status","freshness_class","materiality","finding_value_json","direct_artifact_id","direct_artifact_sha256","source_row_key","source_row_fingerprint","lineage_artifact_ids","calculation_version","policy_version","allowed_wording_template","required_qualifier","prohibited_interpretations","allowed_tiers","tier_eligibility_json","active_limitations","promotion_decision","finding_fingerprint"],[
        {"canonical_property_id":"STH-1","county_parcelid":"1","finding_key":"identity.community_membership","finding_domain":"IDENTITY","finding_status":"FACT","confidence_class":"VERIFIED","qa_status":"PASS","freshness_class":"TIME_INVARIANT","materiality":"CRITICAL","finding_value_json":"{}","direct_artifact_id":"canonical_master","direct_artifact_sha256":"c"*64,"source_row_key":"1","source_row_fingerprint":"d"*64,"lineage_artifact_ids":"canonical_master","calculation_version":"v1","policy_version":"FINDING_POLICY_2","allowed_wording_template":"Allowed","required_qualifier":"Qual","prohibited_interpretations":"x","allowed_tiers":"INTERNAL|AGENT|SELLER|PUBLIC","tier_eligibility_json":"{}","active_limitations":"","promotion_decision":"PROMOTE","finding_fingerprint":"e"*64},
        {"canonical_property_id":"STH-516018120","county_parcelid":"516018120","finding_key":"identity.community_membership","finding_domain":"IDENTITY","finding_status":"FACT","confidence_class":"VERIFIED","qa_status":"PASS","freshness_class":"TIME_INVARIANT","materiality":"CRITICAL","finding_value_json":"{}","direct_artifact_id":"canonical_master","direct_artifact_sha256":"c"*64,"source_row_key":"516018120","source_row_fingerprint":"f"*64,"lineage_artifact_ids":"canonical_master","calculation_version":"v1","policy_version":"FINDING_POLICY_2","allowed_wording_template":"Allowed","required_qualifier":"Qual","prohibited_interpretations":"x","allowed_tiers":"INTERNAL|AGENT|SELLER|PUBLIC","tier_eligibility_json":"{}","active_limitations":"FRONTAGE_UNRESOLVED","promotion_decision":"PROMOTE","finding_fingerprint":"1"*64},
    ])
    elig=tmp_path/"elig.csv"
    rows=[]
    for cid in ("STH-1","STH-516018120"):
        for tier in ("INTERNAL","AGENT","SELLER","PUBLIC"):
            yes = cid=="STH-1" or tier=="INTERNAL"
            rows.append({"canonical_property_id":cid,"county_parcelid":"1" if cid=="STH-1" else "516018120","finding_key":"identity.community_membership","output_tier":tier,"eligible":"YES" if yes else "NO","blocking_reasons":"" if yes else "LIMITED","finding_status":"FACT","confidence_class":"VERIFIED","qa_status":"PASS","freshness_class":"TIME_INVARIANT","policy_version":"FINDING_POLICY_2"})
    write_csv(elig,list(rows[0]),rows)
    policy=tmp_path/"policy.csv"
    write_csv(policy,["finding_key","domain","evidence_type","min_confidence","allowed_tiers","allowed_wording","required_qualifier","prohibited_interpretations","freshness_policy","materiality","policy_version"],[
        {"finding_key":"identity.community_membership","domain":"IDENTITY","evidence_type":"NORMALIZED_FACT","min_confidence":"VERIFIED","allowed_tiers":"INTERNAL|AGENT|SELLER|PUBLIC","allowed_wording":"Allowed","required_qualifier":"Qual","prohibited_interpretations":"x","freshness_policy":"TIME_INVARIANT_UNTIL_EVIDENCE_BACKED_CHANGE","materiality":"CRITICAL","policy_version":"FINDING_POLICY_2"}
    ])
    def sh(p): return hashlib.sha256(p.read_bytes()).hexdigest()
    reg={
      "evidence_materialization_registry_id":"STH-M9-006-EVIDENCE-PASSPORT-FINDINGS-v1.0","version":"1.0.0","status":"FROZEN",
      "passport_population":{"total":2,"partial_property_ids":["STH-516018120"]},
      "findings":{"total":2,"policy_version":"FINDING_POLICY_2"},
      "publication_eligibility":{"decision_rows":8,"internal_eligible":2,"agent_eligible":1,"seller_eligible":1,"public_eligible":1},
      "adopted_governance":{"finding_policy_registry":{"finding_families":1,"raw_sha256":sh(policy)},"passport_summary":{"raw_sha256":sh(summary)},"production_finding_candidates":{"raw_sha256":sh(findings)},"publication_eligibility":{"raw_sha256":sh(elig)}},
      "non_promoted_governed_context":{"m9_005_builder_context":{"property_finding_created":False,"reason":"NO_FINDING_POLICY_2_PROPERTY_FINDING_FAMILY"}},
      "governance":{"create_new_analytical_facts":False,"invent_missing_findings":False,"preserve_allowed_wording":True,"preserve_required_qualifiers":True,"preserve_prohibited_interpretations":True,"preserve_confidence_and_qa":True,"preserve_freshness":True,"preserve_tier_eligibility":True,"preserve_limitations":True,"preserve_lineage":True,"renderer_tier_inference_prohibited":True,"report_rendering_prohibited":True,"publication_prohibited":True}
    }
    rp=tmp_path/"reg.yaml"; rp.write_text(yaml.safe_dump(reg,sort_keys=False))
    return rp,summary,findings,elig,policy


def test_valid_materialization(tmp_path):
    r,s,f,e,p=fixtures(tmp_path)
    a=validate_materialization(r,s,f,e,p)
    assert (a.passports,a.findings,a.eligibility_rows)==(2,2,8)
    assert a.partial_passports==("STH-516018120",)


def test_missing_lineage_fails_closed(tmp_path):
    r,s,f,e,p=fixtures(tmp_path)
    rows=list(csv.DictReader(f.read_text().splitlines())); rows[0]["lineage_artifact_ids"]=""
    write_csv(f,list(rows[0]),rows)
    with pytest.raises(ValueError,match="missing governed field"):
        validate_materialization(r,s,f,e,p)


def test_unknown_finding_family_fails_closed(tmp_path):
    r,s,f,e,p=fixtures(tmp_path)
    rows=list(csv.DictReader(f.read_text().splitlines())); rows[0]["finding_key"]="invented.finding"
    write_csv(f,list(rows[0]),rows)
    with pytest.raises(ValueError,match="unsupported finding family"):
        validate_materialization(r,s,f,e,p)


def test_builder_context_cannot_be_promoted_without_policy(tmp_path):
    r,s,f,e,p=fixtures(tmp_path)
    raw=yaml.safe_load(r.read_text()); raw["non_promoted_governed_context"]["m9_005_builder_context"]["property_finding_created"]=True
    r.write_text(yaml.safe_dump(raw,sort_keys=False))
    with pytest.raises(ValueError,match="builder context promoted"):
        validate_materialization(r,s,f,e,p)


def test_governance_weakening_fails_closed(tmp_path):
    r,s,f,e,p=fixtures(tmp_path)
    raw=yaml.safe_load(r.read_text()); raw["governance"]["preserve_prohibited_interpretations"]=False
    r.write_text(yaml.safe_dump(raw,sort_keys=False))
    with pytest.raises(ValueError,match="governance weakened"):
        validate_materialization(r,s,f,e,p)
