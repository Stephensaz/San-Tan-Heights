import csv
from pathlib import Path

import pytest
import yaml

from src.activation import audit_binding, validate_binding_against_registry


def write_activation(tmp_path):
    path = tmp_path / "activation.csv"
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=(
                "canonical_property_id",
                "county_parcelid",
                "source_freeze_fingerprint",
                "member_lineage_fingerprint",
            ),
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(
            [
                {
                    "canonical_property_id": "STH-509021000",
                    "county_parcelid": "509021000",
                    "source_freeze_fingerprint": "f" * 64,
                    "member_lineage_fingerprint": "a" * 64,
                },
                {
                    "canonical_property_id": "STH-516018120",
                    "county_parcelid": "516018120",
                    "source_freeze_fingerprint": "f" * 64,
                    "member_lineage_fingerprint": "b" * 64,
                },
            ]
        )
    return path


def base_rows():
    return [
        {
            "canonical_property_id": "STH-509021000",
            "county_parcelid": "509021000",
            "m9_002_member_lineage_fingerprint": "a" * 64,
            "recorded_phase": "A-1",
            "phase_group": "A-Series",
            "phase_binding_status": "BOUND",
            "geometry_valid": "YES",
            "geometry_qa_status": "PASS",
            "lot_side_engine_status": "RELEASED",
            "lot_side_qa_status": "PASS",
            "block_binding_status": "BOUND",
            "spatial_binding_status": "BOUND",
            "adjacency_record_count": "4",
            "adjacency_records_sha256": "c" * 64,
        },
        {
            "canonical_property_id": "STH-516018120",
            "county_parcelid": "516018120",
            "m9_002_member_lineage_fingerprint": "b" * 64,
            "recorded_phase": "C-13",
            "phase_group": "C-Series",
            "phase_binding_status": "BOUND",
            "geometry_valid": "YES",
            "geometry_qa_status": "PASS",
            "lot_side_engine_status": "BLOCKED_FRONTAGE_UNRESOLVED",
            "lot_side_qa_status": "REVIEW_REQUIRED",
            "block_binding_status": "UNRESOLVED_FRONTAGE",
            "spatial_binding_status": "PARTIAL_UNRESOLVED",
            "adjacency_record_count": "29",
            "adjacency_records_sha256": "d" * 64,
        },
    ]


def write_binding(tmp_path, rows=None):
    rows = base_rows() if rows is None else rows
    path = tmp_path / "binding.csv"
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0].keys(), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    return path


def write_registry(tmp_path, binding_path):
    audit = audit_binding(binding_path, write_activation(tmp_path))
    payload = {
        "binding_registry_id": "STH-M9-003-IDENTITY-PHASE-SPATIAL-v1.0",
        "version": "1.0.0",
        "status": "FROZEN",
        "community_id": "SAN_TAN_HEIGHTS",
        "inputs": {},
        "artifact": {
            "raw_size_bytes": audit.raw_size_bytes,
            "raw_sha256": audit.raw_sha256,
        },
        "population": {
            "row_count": audit.row_count,
            "unique_canonical_property_ids": audit.unique_canonical_property_ids,
            "unique_county_parcelids": audit.unique_county_parcelids,
            "additions_vs_m9_002": audit.additions_vs_activation,
            "omissions_vs_m9_002": audit.omissions_vs_activation,
            "parcelid_mismatches_vs_m9_002": audit.parcelid_mismatches_vs_activation,
        },
        "phase_binding": {"bound": audit.phase_bound, "unresolved": audit.phase_unresolved},
        "geometry_binding": {"qa_pass": audit.geometry_pass},
        "lot_side_binding": {
            "qa_pass": audit.lot_side_pass,
            "review_required": audit.lot_side_review_required,
        },
        "block_binding": {
            "bound": audit.block_bound,
            "unresolved_frontage": audit.block_unresolved,
        },
        "spatial_binding": {
            "bound": audit.spatial_bound,
            "partial_unresolved": audit.spatial_partial_unresolved,
            "unresolved_property_ids": list(audit.unresolved_property_ids),
            "unresolved_reason": {
                "STH-516018120": "BLOCKED_FRONTAGE_UNRESOLVED"
            },
        },
        "governance": {
            "preserve_upstream_unresolved_states": True,
            "new_phase_inference_prohibited": True,
            "new_spatial_inference_prohibited": True,
            "address_identity_inference_prohibited": True,
            "membership_changes_prohibited": True,
            "report_generation_prohibited": True,
            "publication_prohibited": True,
        },
    }
    path = tmp_path / "registry.yaml"
    path.write_text(yaml.safe_dump(payload, sort_keys=False))
    return path


def test_binding_preserves_complete_identity_and_unresolved_state(tmp_path):
    activation = write_activation(tmp_path)
    binding = write_binding(tmp_path)
    audit = audit_binding(binding, activation)
    assert audit.row_count == 2
    assert audit.additions_vs_activation == 0
    assert audit.omissions_vs_activation == 0
    assert audit.phase_bound == 2
    assert audit.geometry_pass == 2
    assert audit.spatial_bound == 1
    assert audit.spatial_partial_unresolved == 1
    assert audit.unresolved_property_ids == ("STH-516018120",)


def test_binding_rejects_member_lineage_drift(tmp_path):
    activation = write_activation(tmp_path)
    rows = base_rows()
    rows[0]["m9_002_member_lineage_fingerprint"] = "9" * 64
    binding = write_binding(tmp_path, rows)
    with pytest.raises(ValueError, match="M9-002 member lineage mismatch"):
        audit_binding(binding, activation)


def test_binding_rejects_parcel_identity_drift_via_registry(tmp_path):
    activation = write_activation(tmp_path)
    binding = write_binding(tmp_path)
    registry = write_registry(tmp_path, binding)
    rows = base_rows()
    rows[0]["county_parcelid"] = "999999999"
    mutated = write_binding(tmp_path, rows)
    with pytest.raises(ValueError, match="registry count mismatch for parcelid_mismatches"):
        validate_binding_against_registry(registry, mutated, activation)


def test_bound_phase_cannot_be_blank(tmp_path):
    activation = write_activation(tmp_path)
    rows = base_rows()
    rows[0]["recorded_phase"] = ""
    binding = write_binding(tmp_path, rows)
    with pytest.raises(ValueError, match="bound phase has blank"):
        audit_binding(binding, activation)


def test_unresolved_frontage_must_remain_explicit(tmp_path):
    activation = write_activation(tmp_path)
    binding = write_binding(tmp_path)
    registry = write_registry(tmp_path, binding)
    validate_binding_against_registry(registry, binding, activation)

    rows = base_rows()
    rows[1]["block_binding_status"] = "BOUND"
    rows[1]["spatial_binding_status"] = "BOUND"
    resolved = write_binding(tmp_path, rows)
    with pytest.raises(ValueError, match="registry count mismatch|unresolved property set mismatch"):
        validate_binding_against_registry(registry, resolved, activation)


def test_registry_rejects_governance_weakening(tmp_path):
    activation = write_activation(tmp_path)
    binding = write_binding(tmp_path)
    registry = write_registry(tmp_path, binding)
    raw = yaml.safe_load(registry.read_text())
    raw["governance"]["new_spatial_inference_prohibited"] = False
    registry.write_text(yaml.safe_dump(raw, sort_keys=False))
    with pytest.raises(ValueError, match="governance rule"):
        validate_binding_against_registry(registry, binding, activation)
