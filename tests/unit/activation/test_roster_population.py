import csv
from pathlib import Path

import pytest
import yaml

from src.activation import (
    audit_activation_roster,
    build_activation_roster,
    validate_against_registry,
)


def source_rows():
    return [
        {
            "canonical_property_id": "STH-509021000",
            "county_parcelid": "509021000",
        },
        {
            "canonical_property_id": "STH-516010270",
            "county_parcelid": "516010270",
        },
    ]


def write_source(tmp_path, rows=None):
    rows = source_rows() if rows is None else rows
    path = tmp_path / "source.csv"
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["canonical_property_id", "county_parcelid"],
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)
    return path


def write_registry(tmp_path, activation_path, source_path, freeze):
    audit = audit_activation_roster(
        activation_path,
        source_pairs=tuple(sorted((r["canonical_property_id"], r["county_parcelid"]) for r in source_rows())),
        m9_001_freeze_fingerprint=freeze,
    )
    payload = {
        "activation_roster_id": "STH-M9-002-CANONICAL-ROSTER-v1.0",
        "version": "1.0.0",
        "status": "FROZEN",
        "community_id": "SAN_TAN_HEIGHTS",
        "source": {
            "m9_001_freeze_fingerprint": freeze,
            "canonical_roster_raw_sha256": "a" * 64,
            "canonical_master_version": "1.0.0",
        },
        "artifact": {
            "name": activation_path.name,
            "library_file_id": "libfile-test",
            "path": str(activation_path),
            "raw_size_bytes": audit.raw_size_bytes,
            "raw_sha256": audit.raw_sha256,
            "authoritative": False,
        },
        "population": {
            "row_count": audit.row_count,
            "unique_canonical_property_ids": audit.unique_canonical_property_ids,
            "unique_county_parcelids": audit.unique_county_parcelids,
            "additions_vs_m9_001": audit.additions_vs_source,
            "omissions_vs_m9_001": audit.omissions_vs_source,
            "duplicate_canonical_property_ids": audit.duplicate_canonical_property_ids,
            "duplicate_county_parcelids": audit.duplicate_county_parcelids,
            "canonical_property_ids_sha256": audit.canonical_property_ids_sha256,
            "county_parcelids_sha256": audit.county_parcelids_sha256,
            "canonical_property_id_to_parcelid_pairs_sha256": audit.property_parcel_pairs_sha256,
        },
        "lineage": {
            "every_row_has_m9_001_freeze_fingerprint": True,
            "member_lineage_algorithm": "SHA256(canonical_property_id|county_parcelid|m9_001_freeze_fingerprint)",
            "blank_member_lineage_fingerprints": 0,
            "duplicate_member_lineage_fingerprints": 0,
        },
        "governance": {
            "no_address_identity_inference": True,
            "no_phase_enrichment": True,
            "no_spatial_enrichment": True,
            "no_report_generation": True,
            "no_publication": True,
            "exact_membership_preservation_required": True,
            "deterministic_replay_required": True,
        },
    }
    path = tmp_path / "registry.yaml"
    path.write_text(yaml.safe_dump(payload, sort_keys=False))
    return path


def test_population_is_deterministic_and_preserves_membership(tmp_path):
    source = write_source(tmp_path)
    freeze = "f" * 64
    first = tmp_path / "first.csv"
    second = tmp_path / "second.csv"
    first_audit = build_activation_roster(source, first, m9_001_freeze_fingerprint=freeze)
    second_audit = build_activation_roster(source, second, m9_001_freeze_fingerprint=freeze)
    assert first.read_bytes() == second.read_bytes()
    assert first_audit == second_audit
    assert first_audit.row_count == 2
    assert first_audit.additions_vs_source == 0
    assert first_audit.omissions_vs_source == 0


def test_member_lineage_binds_identity_pair_and_freeze(tmp_path):
    source = write_source(tmp_path)
    freeze = "f" * 64
    activation = tmp_path / "activation.csv"
    build_activation_roster(source, activation, m9_001_freeze_fingerprint=freeze)
    rows = list(csv.DictReader(activation.read_text().splitlines()))
    assert all(row["source_freeze_fingerprint"] == freeze for row in rows)
    assert len({row["member_lineage_fingerprint"] for row in rows}) == 2


def test_addition_or_omission_fails_closed(tmp_path):
    source = write_source(tmp_path)
    freeze = "f" * 64
    activation = tmp_path / "activation.csv"
    build_activation_roster(source, activation, m9_001_freeze_fingerprint=freeze)
    rows = list(csv.DictReader(activation.read_text().splitlines()))
    rows = rows[:-1]
    with activation.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0].keys(), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    with pytest.raises(ValueError, match="activation membership mismatch"):
        audit_activation_roster(
            activation,
            source_pairs=tuple(sorted((r["canonical_property_id"], r["county_parcelid"]) for r in source_rows())),
            m9_001_freeze_fingerprint=freeze,
        )


def test_lineage_tampering_fails_closed(tmp_path):
    source = write_source(tmp_path)
    freeze = "f" * 64
    activation = tmp_path / "activation.csv"
    build_activation_roster(source, activation, m9_001_freeze_fingerprint=freeze)
    rows = list(csv.DictReader(activation.read_text().splitlines()))
    rows[0]["source_freeze_fingerprint"] = "e" * 64
    with activation.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0].keys(), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    with pytest.raises(ValueError, match="M9-001 lineage fingerprint mismatch"):
        audit_activation_roster(
            activation,
            source_pairs=tuple(sorted((r["canonical_property_id"], r["county_parcelid"]) for r in source_rows())),
            m9_001_freeze_fingerprint=freeze,
        )


def test_registry_validation_binds_exact_activation_artifact(tmp_path):
    source = write_source(tmp_path)
    freeze = "f" * 64
    activation = tmp_path / "activation.csv"
    build_activation_roster(source, activation, m9_001_freeze_fingerprint=freeze)
    registry = write_registry(tmp_path, activation, source, freeze)
    audit = validate_against_registry(registry, activation, source)
    assert audit.row_count == 2


def test_duplicate_source_identity_cannot_be_populated(tmp_path):
    rows = source_rows()
    rows.append(dict(rows[0]))
    source = write_source(tmp_path, rows)
    with pytest.raises(ValueError, match="duplicate canonical property identity"):
        build_activation_roster(
            source,
            tmp_path / "activation.csv",
            m9_001_freeze_fingerprint="f" * 64,
        )
