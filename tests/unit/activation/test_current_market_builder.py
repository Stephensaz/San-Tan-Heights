import csv
from pathlib import Path

import pytest
import yaml

from src.activation import audit_current_context


def write_csv(path, fieldnames, rows):
    with path.open("w", newline="", encoding="utf-8") as h:
        w=csv.DictWriter(h,fieldnames=fieldnames,lineterminator="\n"); w.writeheader(); w.writerows(rows)


def fixtures(tmp_path):
    prop=tmp_path/"prop.csv"
    write_csv(prop,[
        "canonical_property_id","county_parcelid","m9_003_spatial_binding_status","current_context_status",
        "snapshot_date","snapshot_freshness_state","snapshot_age_days",
        "currently_available_close_substitute_property_count","currently_available_strict_substitute_property_count",
        "currently_marketed_under_contract_close_substitute_property_count","current_available_property_universe_count",
        "current_marketed_under_contract_property_universe_count","snapshot_source_mode","source_qa_status","unavailable_reason"
    ],[
        {"canonical_property_id":"STH-1","county_parcelid":"1","m9_003_spatial_binding_status":"BOUND","current_context_status":"AVAILABLE","snapshot_date":"2026-09-14","snapshot_freshness_state":"CURRENT","snapshot_age_days":"3","currently_available_close_substitute_property_count":"2","currently_available_strict_substitute_property_count":"1","currently_marketed_under_contract_close_substitute_property_count":"0","current_available_property_universe_count":"53","current_marketed_under_contract_property_universe_count":"5","snapshot_source_mode":"FINAL_STATE_SNAPSHOT","source_qa_status":"PASS","unavailable_reason":""},
        {"canonical_property_id":"STH-516018120","county_parcelid":"516018120","m9_003_spatial_binding_status":"PARTIAL_UNRESOLVED","current_context_status":"UNAVAILABLE","snapshot_date":"2026-09-14","snapshot_freshness_state":"CURRENT","snapshot_age_days":"3","currently_available_close_substitute_property_count":"","currently_available_strict_substitute_property_count":"","currently_marketed_under_contract_close_substitute_property_count":"","current_available_property_universe_count":"53","current_marketed_under_contract_property_universe_count":"5","snapshot_source_mode":"FINAL_STATE_SNAPSHOT","source_qa_status":"NOT_APPLICABLE","unavailable_reason":"UPSTREAM_SPATIAL_FRONTAGE_UNRESOLVED"},
    ])
    builder=tmp_path/"builder.csv"
    write_csv(builder,["builder_context_id","competition_type","builder","community","offering","price_or_start","sqft_or_range","availability","incentive_or_positioning","source_url","seller_competition_note","source_as_of","snapshot_freshness_state","snapshot_age_days","offer_validity_state","explicit_offer_end_date","direct_in_community"],[
        {"builder_context_id":"BC-001","competition_type":"DIRECT IN-COMMUNITY NEW HOME","builder":"X","community":"Pinnacle","offering":"QMI","price_or_start":"$500k","sqft_or_range":"2200","availability":"Ready","incentive_or_positioning":"Savings","source_url":"x","seller_competition_note":"x","source_as_of":"2026-09-14","snapshot_freshness_state":"CURRENT","snapshot_age_days":"3","offer_validity_state":"NO_EXPLICIT_END_DATE","explicit_offer_end_date":"","direct_in_community":"YES"},
        {"builder_context_id":"BC-006","competition_type":"NEARBY NEW CONSTRUCTION","builder":"Y","community":"Wildera","offering":"QMI","price_or_start":"$380k","sqft_or_range":"1600","availability":"Current","incentive_or_positioning":"Promo through Sep 15","source_url":"y","seller_competition_note":"y","source_as_of":"2026-09-14","snapshot_freshness_state":"CURRENT","snapshot_age_days":"3","offer_validity_state":"EXPIRED_BY_EXPLICIT_SOURCE_DATE","explicit_offer_end_date":"2026-09-15","direct_in_community":"NO"},
    ])
    import hashlib
    reg={
      "current_context_registry_id":"STH-M9-005-CURRENT-MARKET-BUILDER-v1.0","version":"1.0.0","status":"FROZEN","community_id":"SAN_TAN_HEIGHTS","evaluation_date":"2026-09-17",
      "freshness_policy":{"cadence":"WEEKLY","snapshot_max_age_days":7,"freshness_state_within_cadence":"CURRENT"},
      "inputs":{},"artifacts":{"property_context":{"raw_sha256":hashlib.sha256(prop.read_bytes()).hexdigest()},"builder_context":{"raw_sha256":hashlib.sha256(builder.read_bytes()).hexdigest()}},
      "property_population":{"corpus_members":2,"current_context_available":1,"current_context_unavailable":1,"unavailable_property_ids":["STH-516018120"],"unavailable_reason":{"STH-516018120":"UPSTREAM_SPATIAL_FRONTAGE_UNRESOLVED"},"snapshot_age_days_at_evaluation":3},
      "builder_context":{"alternatives":2,"explicit_offer_end_dates":{"expired_as_of_evaluation":1}},
      "governance":{k:True for k in ["historical_layer_immutable","preserve_source_values","preserve_source_dates","preserve_source_qa_states","stale_or_unavailable_states_explicit","expired_offer_terms_not_carried_forward_as_current","property_specific_builder_substitution_inference_prohibited","new_pricing_conclusions_prohibited","new_value_opinions_prohibited","current_market_refresh_outside_frozen_snapshot_prohibited","report_generation_prohibited","publication_prohibited"]}
    }
    rp=tmp_path/"reg.yaml"; rp.write_text(yaml.safe_dump(reg,sort_keys=False))
    return rp,prop,builder


def test_valid_current_context(tmp_path):
    r,p,b=fixtures(tmp_path)
    a=audit_current_context(r,p,b)
    assert (a.corpus_members,a.available,a.unavailable,a.expired_builder_offer_terms)==(2,1,1,1)


def test_unavailable_context_cannot_gain_inferred_counts(tmp_path):
    r,p,b=fixtures(tmp_path)
    rows=list(csv.DictReader(p.read_text().splitlines())); rows[1]["currently_available_close_substitute_property_count"]="1"
    write_csv(p,list(rows[0]),rows)
    with pytest.raises(ValueError,match="unavailable context contains inferred counts"):
        audit_current_context(r,p,b)


def test_expired_offer_cannot_be_carried_as_current(tmp_path):
    r,p,b=fixtures(tmp_path)
    rows=list(csv.DictReader(b.read_text().splitlines())); rows[1]["offer_validity_state"]="VALID_BY_EXPLICIT_SOURCE_DATE"
    write_csv(b,list(rows[0]),rows)
    with pytest.raises(ValueError,match="explicit offer validity mismatch"):
        audit_current_context(r,p,b)


def test_freshness_age_must_match_dates(tmp_path):
    r,p,b=fixtures(tmp_path)
    rows=list(csv.DictReader(p.read_text().splitlines())); rows[0]["snapshot_age_days"]="2"
    write_csv(p,list(rows[0]),rows)
    with pytest.raises(ValueError,match="snapshot age mismatch"):
        audit_current_context(r,p,b)


def test_governance_weakening_fails_closed(tmp_path):
    r,p,b=fixtures(tmp_path)
    raw=yaml.safe_load(r.read_text()); raw["governance"]["new_pricing_conclusions_prohibited"]=False; r.write_text(yaml.safe_dump(raw,sort_keys=False))
    with pytest.raises(ValueError,match="governance weakened"):
        audit_current_context(r,p,b)
