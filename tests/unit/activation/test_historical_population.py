import csv
from pathlib import Path

import pytest
import yaml

from src.activation import audit_historical_population


def write_property_population(tmp_path, rows=None):
    rows = rows or [
        {
            "canonical_property_id": "STH-509021000",
            "county_parcelid": "509021000",
            "m9_003_spatial_binding_status": "BOUND",
            "history_population_status": "GOVERNED_HISTORY_AVAILABLE",
            "governed_listing_record_count": "2",
            "governed_listing_ids_sha256": "a" * 64,
            "initial_availability_window_count": "1",
            "initial_availability_listing_ids_sha256": "b" * 64,
            "historical_replay_anchor_count": "3",
            "historical_replay_anchor_ids_sha256": "c" * 64,
            "legacy_bound_episode_count": "1",
            "legacy_bound_episode_ids_sha256": "d" * 64,
            "verified_master_history_flag": "YES",
            "verified_master_listing_count": "2",
            "complete_event_history_available": "NO",
            "historical_price_path_available": "NO",
            "timeline_scope_limit": "INITIAL_AVAILABLE_WINDOW_ONLY_WHEN_ELIGIBLE;NOT_COMPLETE_EVENT_HISTORY",
        },
        {
            "canonical_property_id": "STH-509021010",
            "county_parcelid": "509021010",
            "m9_003_spatial_binding_status": "BOUND",
            "history_population_status": "NO_GOVERNED_HISTORY",
            "governed_listing_record_count": "0",
            "governed_listing_ids_sha256": "",
            "initial_availability_window_count": "0",
            "initial_availability_listing_ids_sha256": "",
            "historical_replay_anchor_count": "0",
            "historical_replay_anchor_ids_sha256": "",
            "legacy_bound_episode_count": "0",
            "legacy_bound_episode_ids_sha256": "",
            "verified_master_history_flag": "NO",
            "verified_master_listing_count": "0",
            "complete_event_history_available": "NOT_APPLICABLE",
            "historical_price_path_available": "NOT_APPLICABLE",
            "timeline_scope_limit": "NO_GOVERNED_HISTORY",
        },
    ]
    path = tmp_path / "property.csv"
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0].keys(), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    return path


def write_bridge(tmp_path, rows=None):
    rows = rows or [
        {
            "episode_id": "STH-CAND-00001-E01",
            "candidate_property_id": "STH-CAND-00001",
            "canonical_property_id": "STH-509021000",
            "county_parcelid": "509021000",
            "episode_qa": "A - Valid",
            "method_version": "v0.8-2026-09-14",
            "binding_status": "BOUND_CANONICAL_APN",
            "identity_resolution_status_frozen": "COUNTY VERIFIED",
            "exception_bucket": "",
            "first_list_date": "2004-01-01",
            "last_end_date": "2004-02-01",
            "listing_attempts": "1",
            "closed_flag": "YES",
        },
        {
            "episode_id": "STH-CAND-00002-E01",
            "candidate_property_id": "STH-CAND-00002",
            "canonical_property_id": "",
            "county_parcelid": "",
            "episode_qa": "A - Valid",
            "method_version": "v0.8-2026-09-14",
            "binding_status": "UNRESOLVED_NON_PROMOTED",
            "identity_resolution_status_frozen": "NO CONFLICT GROUP",
            "exception_bucket": "LIKELY SAN TAN HEIGHTS - BAD/MISSING APN",
            "first_list_date": "2005-01-01",
            "last_end_date": "2005-02-01",
            "listing_attempts": "1",
            "closed_flag": "YES",
        },
    ]
    path = tmp_path / "bridge.csv"
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0].keys(), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    return path


def write_registry(tmp_path, prop, bridge):
    import hashlib
    payload = {
        "historical_population_registry_id": "STH-M9-004-HISTORICAL-INTELLIGENCE-v1.0",
        "version": "1.0.0",
        "status": "FROZEN",
        "community_id": "SAN_TAN_HEIGHTS",
        "inputs": {},
        "artifacts": {
            "property_population": {"raw_sha256": hashlib.sha256(prop.read_bytes()).hexdigest()},
            "legacy_episode_bridge": {"raw_sha256": hashlib.sha256(bridge.read_bytes()).hexdigest()},
        },
        "population": {
            "corpus_members": 2,
            "history_available_properties": 1,
            "no_governed_history_properties": 1,
            "canonical_listing_records_attached": 2,
            "initial_availability_windows_attached": 1,
            "replay_anchors_attached": 3,
        },
        "legacy_episode_identity": {
            "bound_to_canonical_property": 1,
            "unresolved_non_promoted": 1,
        },
        "governance": {
            "preserve_listing_identity": True,
            "preserve_legacy_episode_identity": True,
            "unresolved_history_non_promoted": True,
            "address_only_identity_substitution_prohibited": True,
            "new_episode_splitting_or_merging_prohibited": True,
            "new_price_interpretation_prohibited": True,
            "new_market_behavior_inference_prohibited": True,
            "recompute_analytical_studies_prohibited": True,
            "no_history_stays_explicit": True,
            "current_market_refresh_prohibited": True,
            "report_generation_prohibited": True,
            "publication_prohibited": True,
        },
    }
    path = tmp_path / "registry.yaml"
    path.write_text(yaml.safe_dump(payload, sort_keys=False))
    return path


def test_historical_population_preserves_available_and_no_history_states(tmp_path):
    prop = write_property_population(tmp_path)
    bridge = write_bridge(tmp_path)
    registry = write_registry(tmp_path, prop, bridge)
    audit = audit_historical_population(registry, prop, bridge)
    assert audit.corpus_members == 2
    assert audit.history_available_properties == 1
    assert audit.no_history_properties == 1
    assert audit.canonical_listing_records == 2
    assert audit.legacy_bound_episodes == 1
    assert audit.legacy_unresolved_episodes == 1


def test_no_history_cannot_silently_gain_listing_count(tmp_path):
    rows = None
    prop = write_property_population(tmp_path, rows)
    data = list(csv.DictReader(prop.read_text().splitlines()))
    data[1]["governed_listing_record_count"] = "1"
    prop = write_property_population(tmp_path, data)
    bridge = write_bridge(tmp_path)
    registry = write_registry(tmp_path, prop, bridge)
    with pytest.raises(ValueError, match="invalid no-history state|listing count disagrees"):
        audit_historical_population(registry, prop, bridge)


def test_unresolved_legacy_episode_cannot_be_promoted(tmp_path):
    prop = write_property_population(tmp_path)
    bridge = write_bridge(tmp_path)
    data = list(csv.DictReader(bridge.read_text().splitlines()))
    data[1]["canonical_property_id"] = "STH-509021010"
    bridge = write_bridge(tmp_path, data)
    registry = write_registry(tmp_path, prop, bridge)
    with pytest.raises(ValueError, match="unresolved legacy episode was promoted"):
        audit_historical_population(registry, prop, bridge)


def test_duplicate_episode_id_fails_closed(tmp_path):
    prop = write_property_population(tmp_path)
    bridge = write_bridge(tmp_path)
    data = list(csv.DictReader(bridge.read_text().splitlines()))
    data[1]["episode_id"] = data[0]["episode_id"]
    bridge = write_bridge(tmp_path, data)
    registry = write_registry(tmp_path, prop, bridge)
    with pytest.raises(ValueError, match="duplicate legacy episode identity"):
        audit_historical_population(registry, prop, bridge)


def test_history_timeline_limitation_cannot_be_removed(tmp_path):
    prop = write_property_population(tmp_path)
    data = list(csv.DictReader(prop.read_text().splitlines()))
    data[0]["timeline_scope_limit"] = "COMPLETE_HISTORY"
    prop = write_property_population(tmp_path, data)
    bridge = write_bridge(tmp_path)
    registry = write_registry(tmp_path, prop, bridge)
    with pytest.raises(ValueError, match="timeline limitation drift"):
        audit_historical_population(registry, prop, bridge)


def test_governance_weakening_fails_closed(tmp_path):
    prop = write_property_population(tmp_path)
    bridge = write_bridge(tmp_path)
    registry = write_registry(tmp_path, prop, bridge)
    raw = yaml.safe_load(registry.read_text())
    raw["governance"]["new_episode_splitting_or_merging_prohibited"] = False
    registry.write_text(yaml.safe_dump(raw, sort_keys=False))
    with pytest.raises(ValueError, match="governance weakened"):
        audit_historical_population(registry, prop, bridge)
