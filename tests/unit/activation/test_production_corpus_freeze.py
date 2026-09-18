import csv
from hashlib import sha256
from pathlib import Path

import pytest
import yaml

from src.activation import ProductionCorpusFreezeValidator


def write_roster(tmp_path, rows):
    path = tmp_path / "roster.csv"
    fieldnames = [
        "canonical_property_id",
        "county_parcelid",
        "community_membership_status",
        "parcel_role",
        "canonical_master_version",
        "membership_change_policy",
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    return path


def hashes(path):
    raw = path.read_bytes()
    rows = list(csv.DictReader(raw.decode("utf-8-sig").splitlines()))
    ids = [row["canonical_property_id"] for row in rows]
    parcels = [row["county_parcelid"] for row in rows]
    pairs = sorted(zip(ids, parcels))
    return {
        "raw_size_bytes": len(raw),
        "raw_sha256": sha256(raw).hexdigest(),
        "canonical_property_ids_sha256": sha256(
            ("\n".join(sorted(ids)) + "\n").encode()
        ).hexdigest(),
        "county_parcelids_sha256": sha256(
            ("\n".join(sorted(parcels)) + "\n").encode()
        ).hexdigest(),
        "pairs_sha256": sha256(
            ("\n".join(f"{a},{b}" for a, b in pairs) + "\n").encode()
        ).hexdigest(),
        "count": len(rows),
    }


def write_registry(tmp_path, roster_path, *, admitted=None):
    h = hashes(roster_path)
    admitted = h["count"] if admitted is None else admitted
    payload = {
        "production_corpus_freeze_id": "STH-PRODUCTION-CORPUS-FREEZE-v1.0",
        "version": "1.0.0",
        "status": "FROZEN",
        "community_id": "SAN_TAN_HEIGHTS",
        "canonical_roster": {
            "name": "roster.csv",
            "canonical_master_version": "1.0.0",
            "original_library_file_id": "libfile-test",
            "original_library_version": "1",
            "raw_size_bytes": h["raw_size_bytes"],
            "raw_sha256": h["raw_sha256"],
        },
        "membership": {
            "declared_total": h["count"],
            "canonical_property_id_count": h["count"],
            "unique_canonical_property_id_count": h["count"],
            "county_parcelid_count": h["count"],
            "unique_county_parcelid_count": h["count"],
            "blank_canonical_property_id_count": 0,
            "blank_county_parcelid_count": 0,
            "canonical_property_ids_sha256": h["canonical_property_ids_sha256"],
            "county_parcelids_sha256": h["county_parcelids_sha256"],
            "canonical_property_id_to_parcelid_pairs_sha256": h["pairs_sha256"],
        },
        "admission": {
            "admitted": admitted,
            "quarantined": 0,
            "excluded_with_governed_reason": 0,
            "admission_basis": {
                "community_membership_status": "VERIFIED_RECORDED_SAN_TAN_HEIGHTS",
                "parcel_role": "RESIDENTIAL_LOT",
                "canonical_master_version": "1.0.0",
            },
        },
        "quality": {
            "all_members_verified_recorded_san_tan_heights": True,
            "all_members_residential_lot": True,
            "all_members_master_version_1_0_0": True,
            "one_to_one_canonical_id_parcelid": True,
            "duplicate_canonical_property_ids": 0,
            "duplicate_county_parcelids": 0,
            "missing_canonical_property_ids": 0,
            "missing_county_parcelids": 0,
        },
        "upstream_certification": {},
        "governance": {
            "membership_payload_is_canonical_csv": True,
            "duplicate_roster_prohibited": True,
            "membership_changes_require_evidence_backed_change_event": True,
            "all_members_accounted": True,
            "conditional_go_prohibited": True,
        },
    }
    path = tmp_path / "freeze.yaml"
    path.write_text(yaml.safe_dump(payload, sort_keys=False))
    return path


@pytest.fixture
def valid_rows():
    return [
        {
            "canonical_property_id": "STH-509021000",
            "county_parcelid": "509021000",
            "community_membership_status": "VERIFIED_RECORDED_SAN_TAN_HEIGHTS",
            "parcel_role": "RESIDENTIAL_LOT",
            "canonical_master_version": "1.0.0",
            "membership_change_policy": "EVIDENCE_BACKED_CHANGE_EVENT_REQUIRED",
        },
        {
            "canonical_property_id": "STH-516010270",
            "county_parcelid": "516010270",
            "community_membership_status": "VERIFIED_RECORDED_SAN_TAN_HEIGHTS",
            "parcel_role": "RESIDENTIAL_LOT",
            "canonical_master_version": "1.0.0",
            "membership_change_policy": "EVIDENCE_BACKED_CHANGE_EVENT_REQUIRED",
        },
    ]


def test_exact_roster_snapshot_validates_and_fingerprints(tmp_path, valid_rows):
    roster = write_roster(tmp_path, valid_rows)
    registry = write_registry(tmp_path, roster)
    freeze = ProductionCorpusFreezeValidator().validate(registry, roster)
    assert freeze.declared_total == 2
    assert freeze.admitted == 2
    assert freeze.quarantined == 0
    assert freeze.excluded == 0
    assert len(freeze.fingerprint) == 64


def test_byte_level_mutation_fails_closed(tmp_path, valid_rows):
    roster = write_roster(tmp_path, valid_rows)
    registry = write_registry(tmp_path, roster)
    roster.write_bytes(roster.read_bytes() + b"\n")
    with pytest.raises(ValueError, match="byte size mismatch|SHA-256 mismatch"):
        ProductionCorpusFreezeValidator().validate(registry, roster)


def test_duplicate_identity_fails_closed_even_if_registry_is_rehashed(tmp_path, valid_rows):
    rows = [valid_rows[0], dict(valid_rows[0])]
    roster = write_roster(tmp_path, rows)
    registry = write_registry(tmp_path, roster)
    with pytest.raises(ValueError, match="duplicate canonical property identity"):
        ProductionCorpusFreezeValidator().validate(registry, roster)


def test_nonresidential_member_fails_closed(tmp_path, valid_rows):
    rows = [dict(valid_rows[0]), dict(valid_rows[1])]
    rows[1]["parcel_role"] = "COMMON_AREA"
    roster = write_roster(tmp_path, rows)
    registry = write_registry(tmp_path, roster)
    with pytest.raises(ValueError, match="non-residential parcel"):
        ProductionCorpusFreezeValidator().validate(registry, roster)


def test_unverified_membership_fails_closed(tmp_path, valid_rows):
    rows = [dict(valid_rows[0]), dict(valid_rows[1])]
    rows[1]["community_membership_status"] = "UNRESOLVED"
    roster = write_roster(tmp_path, rows)
    registry = write_registry(tmp_path, roster)
    with pytest.raises(ValueError, match="non-verified community member"):
        ProductionCorpusFreezeValidator().validate(registry, roster)


def test_admission_count_must_equal_exact_membership(tmp_path, valid_rows):
    roster = write_roster(tmp_path, valid_rows)
    registry = write_registry(tmp_path, roster, admitted=1)
    with pytest.raises(ValueError, match="admitted count"):
        ProductionCorpusFreezeValidator().validate(registry, roster)


def test_membership_change_policy_drift_fails_closed(tmp_path, valid_rows):
    rows = [dict(valid_rows[0]), dict(valid_rows[1])]
    rows[1]["membership_change_policy"] = "FREEFORM_CHANGE"
    roster = write_roster(tmp_path, rows)
    registry = write_registry(tmp_path, roster)
    with pytest.raises(ValueError, match="membership change policy drift"):
        ProductionCorpusFreezeValidator().validate(registry, roster)
