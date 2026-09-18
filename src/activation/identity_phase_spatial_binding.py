from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import csv
from pathlib import Path
from typing import Mapping

import yaml


@dataclass(frozen=True)
class BindingAudit:
    row_count: int
    unique_canonical_property_ids: int
    unique_county_parcelids: int
    additions_vs_activation: int
    omissions_vs_activation: int
    parcelid_mismatches_vs_activation: int
    phase_bound: int
    phase_unresolved: int
    geometry_pass: int
    lot_side_pass: int
    lot_side_review_required: int
    block_bound: int
    block_unresolved: int
    spatial_bound: int
    spatial_partial_unresolved: int
    unresolved_property_ids: tuple[str, ...]
    raw_size_bytes: int
    raw_sha256: str


def _read_csv(path: str | Path) -> list[dict[str, str]]:
    raw = Path(path).read_bytes()
    return list(csv.DictReader(raw.decode("utf-8-sig").splitlines()))


def audit_binding(
    binding_path: str | Path,
    activation_roster_path: str | Path,
) -> BindingAudit:
    binding_path = Path(binding_path)
    raw = binding_path.read_bytes()
    rows = list(csv.DictReader(raw.decode("utf-8").splitlines()))
    activation = _read_csv(activation_roster_path)

    required = {
        "canonical_property_id",
        "county_parcelid",
        "m9_002_member_lineage_fingerprint",
        "recorded_phase",
        "phase_group",
        "phase_binding_status",
        "geometry_valid",
        "geometry_qa_status",
        "lot_side_engine_status",
        "lot_side_qa_status",
        "block_binding_status",
        "spatial_binding_status",
        "adjacency_record_count",
        "adjacency_records_sha256",
    }
    if not rows or not required <= set(rows[0]):
        raise ValueError("M9-003 binding artifact missing required columns")

    activation_map = {
        row["canonical_property_id"]: row for row in activation
    }
    binding_map = {
        row["canonical_property_id"]: row for row in rows
    }

    if len(binding_map) != len(rows):
        raise ValueError("duplicate canonical property identity in M9-003 binding")
    if len({row["county_parcelid"] for row in rows}) != len(rows):
        raise ValueError("duplicate county ParcelID in M9-003 binding")

    activation_ids = set(activation_map)
    binding_ids = set(binding_map)
    additions = binding_ids - activation_ids
    omissions = activation_ids - binding_ids

    parcel_mismatches = 0
    phase_bound = 0
    phase_unresolved = 0
    geometry_pass = 0
    lot_side_pass = 0
    lot_side_review = 0
    block_bound = 0
    block_unresolved = 0
    spatial_bound = 0
    spatial_partial = 0
    unresolved_ids: list[str] = []

    for property_id in sorted(binding_ids & activation_ids):
        row = binding_map[property_id]
        source = activation_map[property_id]

        if row["county_parcelid"] != source["county_parcelid"]:
            parcel_mismatches += 1
        if row["m9_002_member_lineage_fingerprint"] != source["member_lineage_fingerprint"]:
            raise ValueError(f"{property_id}: M9-002 member lineage mismatch")

        if row["phase_binding_status"] == "BOUND":
            if not row["recorded_phase"] or not row["phase_group"]:
                raise ValueError(f"{property_id}: bound phase has blank governed value")
            phase_bound += 1
        else:
            phase_unresolved += 1

        if row["geometry_valid"] == "YES" and row["geometry_qa_status"] == "PASS":
            geometry_pass += 1
        else:
            raise ValueError(f"{property_id}: geometry is not governed PASS")

        if row["lot_side_qa_status"] == "PASS":
            lot_side_pass += 1
        elif row["lot_side_qa_status"] == "REVIEW_REQUIRED":
            lot_side_review += 1
        else:
            raise ValueError(f"{property_id}: unsupported lot-side QA state")

        if row["block_binding_status"] == "BOUND":
            block_bound += 1
        elif row["block_binding_status"] == "UNRESOLVED_FRONTAGE":
            block_unresolved += 1
        else:
            raise ValueError(f"{property_id}: unsupported block binding state")

        if row["spatial_binding_status"] == "BOUND":
            spatial_bound += 1
        elif row["spatial_binding_status"] == "PARTIAL_UNRESOLVED":
            spatial_partial += 1
            unresolved_ids.append(property_id)
        else:
            raise ValueError(f"{property_id}: unsupported spatial binding state")

        count = int(row["adjacency_record_count"])
        digest = row["adjacency_records_sha256"]
        if count < 0 or len(digest) != 64:
            raise ValueError(f"{property_id}: invalid adjacency lineage binding")

    return BindingAudit(
        row_count=len(rows),
        unique_canonical_property_ids=len(binding_map),
        unique_county_parcelids=len({row["county_parcelid"] for row in rows}),
        additions_vs_activation=len(additions),
        omissions_vs_activation=len(omissions),
        parcelid_mismatches_vs_activation=parcel_mismatches,
        phase_bound=phase_bound,
        phase_unresolved=phase_unresolved,
        geometry_pass=geometry_pass,
        lot_side_pass=lot_side_pass,
        lot_side_review_required=lot_side_review,
        block_bound=block_bound,
        block_unresolved=block_unresolved,
        spatial_bound=spatial_bound,
        spatial_partial_unresolved=spatial_partial,
        unresolved_property_ids=tuple(sorted(unresolved_ids)),
        raw_size_bytes=len(raw),
        raw_sha256=sha256(raw).hexdigest(),
    )


def validate_binding_against_registry(
    registry_path: str | Path,
    binding_path: str | Path,
    activation_roster_path: str | Path,
) -> BindingAudit:
    registry = yaml.safe_load(Path(registry_path).read_text())
    if registry.get("binding_registry_id") != "STH-M9-003-IDENTITY-PHASE-SPATIAL-v1.0":
        raise ValueError("unexpected M9-003 binding registry id")
    if str(registry.get("version")) != "1.0.0" or registry.get("status") != "FROZEN":
        raise ValueError("M9-003 binding registry must be FROZEN v1.0.0")

    audit = audit_binding(binding_path, activation_roster_path)
    artifact = registry["artifact"]
    population = registry["population"]
    phase = registry["phase_binding"]
    geometry = registry["geometry_binding"]
    lot = registry["lot_side_binding"]
    block = registry["block_binding"]
    spatial = registry["spatial_binding"]
    governance = registry["governance"]

    exact_checks = (
        ("row_count", population["row_count"], audit.row_count),
        ("unique_canonical_property_ids", population["unique_canonical_property_ids"], audit.unique_canonical_property_ids),
        ("unique_county_parcelids", population["unique_county_parcelids"], audit.unique_county_parcelids),
        ("additions_vs_m9_002", population["additions_vs_m9_002"], audit.additions_vs_activation),
        ("omissions_vs_m9_002", population["omissions_vs_m9_002"], audit.omissions_vs_activation),
        ("parcelid_mismatches_vs_m9_002", population["parcelid_mismatches_vs_m9_002"], audit.parcelid_mismatches_vs_activation),
        ("phase_bound", phase["bound"], audit.phase_bound),
        ("phase_unresolved", phase["unresolved"], audit.phase_unresolved),
        ("geometry_qa_pass", geometry["qa_pass"], audit.geometry_pass),
        ("lot_side_qa_pass", lot["qa_pass"], audit.lot_side_pass),
        ("lot_side_review_required", lot["review_required"], audit.lot_side_review_required),
        ("block_bound", block["bound"], audit.block_bound),
        ("block_unresolved_frontage", block["unresolved_frontage"], audit.block_unresolved),
        ("spatial_bound", spatial["bound"], audit.spatial_bound),
        ("spatial_partial_unresolved", spatial["partial_unresolved"], audit.spatial_partial_unresolved),
    )
    for name, expected, actual in exact_checks:
        if expected != actual:
            raise ValueError(
                f"M9-003 registry count mismatch for {name}: expected={expected}, actual={actual}"
            )

    if tuple(spatial["unresolved_property_ids"]) != audit.unresolved_property_ids:
        raise ValueError("M9-003 unresolved property set mismatch")
    if spatial["unresolved_reason"].get("STH-516018120") != "BLOCKED_FRONTAGE_UNRESOLVED":
        raise ValueError("M9-003 unresolved reason drift")

    if artifact["raw_size_bytes"] != audit.raw_size_bytes:
        raise ValueError("M9-003 binding artifact raw size mismatch")
    if artifact["raw_sha256"] != audit.raw_sha256:
        raise ValueError("M9-003 binding artifact SHA-256 mismatch")

    required_true = (
        "preserve_upstream_unresolved_states",
        "new_phase_inference_prohibited",
        "new_spatial_inference_prohibited",
        "address_identity_inference_prohibited",
        "membership_changes_prohibited",
        "report_generation_prohibited",
        "publication_prohibited",
    )
    if any(governance.get(key) is not True for key in required_true):
        raise ValueError("M9-003 governance rule must remain fail-closed")

    return audit
