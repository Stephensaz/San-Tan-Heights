import json
from pathlib import Path

import pytest

from src.activation import ProductionCorpusManifestLoader

ROOT = Path(__file__).resolve().parents[3]
SCHEMA = ROOT / "schemas" / "activation" / "production-corpus-manifest-v1.0.schema.json"


def write_manifest(tmp_path, members, snapshots=None, status="FROZEN", declared_total=None):
    payload = {
        "manifest_id": "STH-PRODUCTION-CORPUS-v1.0",
        "version": "1.0.0",
        "status": status,
        "community_id": "SAN_TAN_HEIGHTS",
        "declared_total": len(members) if declared_total is None else declared_total,
        "source_snapshots": snapshots
        or [
            {
                "snapshot_id": "canonical-roster-2026-09-18",
                "source_kind": "CANONICAL_PROPERTY_ROSTER",
                "authority": "San Tan Heights governed canonical identity layer",
                "captured_at": "2026-09-18T00:00:00Z",
                "sha256": "a" * 64,
            }
        ],
        "members": members,
    }
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(payload))
    return path


def member(
    property_id,
    *,
    state="ADMITTED",
    quarantine_reasons=None,
    exclusion_reason=None,
    lineage_refs=None,
):
    return {
        "canonical_property_id": property_id,
        "county_parcelid": property_id.removeprefix("STH-"),
        "admission_state": state,
        "quarantine_reasons": quarantine_reasons or [],
        "exclusion_reason": exclusion_reason,
        "lineage_refs": lineage_refs or ["canonical-roster-2026-09-18"],
    }


def loader():
    return ProductionCorpusManifestLoader(SCHEMA)


def test_frozen_manifest_has_deterministic_membership_fingerprint(tmp_path):
    first_path = write_manifest(
        tmp_path,
        [member("STH-516010270"), member("STH-509125700")],
    )
    first = loader().load(first_path)

    second_path = write_manifest(
        tmp_path,
        [member("STH-509125700"), member("STH-516010270")],
    )
    second = loader().load(second_path)

    assert first.fingerprint == second.fingerprint
    assert first.declared_total == 2
    assert first.state_counts["ADMITTED"] == 2


def test_duplicate_canonical_identity_fails_closed(tmp_path):
    path = write_manifest(
        tmp_path,
        [member("STH-516010270"), member("STH-516010270")],
    )
    with pytest.raises(ValueError, match="duplicate canonical property identity"):
        loader().load(path)


def test_declared_total_must_equal_exact_membership(tmp_path):
    path = write_manifest(tmp_path, [member("STH-516010270")], declared_total=2)
    with pytest.raises(ValueError, match="declared_total"):
        loader().load(path)


def test_unknown_lineage_snapshot_fails_closed(tmp_path):
    path = write_manifest(
        tmp_path,
        [member("STH-516010270", lineage_refs=["missing-snapshot"])],
    )
    with pytest.raises(ValueError, match="unknown source snapshot"):
        loader().load(path)


def test_quarantined_record_requires_governed_reason(tmp_path):
    payload = member("STH-516010270", state="QUARANTINED")
    path = write_manifest(tmp_path, [payload])
    with pytest.raises(Exception):
        loader().load(path)

    path = write_manifest(
        tmp_path,
        [
            member(
                "STH-516010270",
                state="QUARANTINED",
                quarantine_reasons=["IDENTITY_UNRESOLVED"],
            )
        ],
    )
    loaded = loader().load(path)
    assert loaded.state_counts["QUARANTINED"] == 1


def test_excluded_record_requires_governed_exclusion_reason(tmp_path):
    path = write_manifest(
        tmp_path,
        [
            member(
                "STH-516010270",
                state="EXCLUDED_WITH_GOVERNED_REASON",
                exclusion_reason="NON_RESIDENTIAL_OR_COMMON_AREA",
            )
        ],
    )
    loaded = loader().load(path)
    assert loaded.state_counts["EXCLUDED_WITH_GOVERNED_REASON"] == 1


def test_admitted_record_cannot_carry_exception_reason(tmp_path):
    path = write_manifest(
        tmp_path,
        [
            member(
                "STH-516010270",
                state="ADMITTED",
                quarantine_reasons=["IDENTITY_UNRESOLVED"],
            )
        ],
    )
    with pytest.raises(Exception):
        loader().load(path)


def test_unfrozen_manifest_cannot_be_used_as_production_corpus(tmp_path):
    path = write_manifest(tmp_path, [member("STH-516010270")], status="DRAFT")
    with pytest.raises(ValueError, match="must be FROZEN"):
        loader().load(path)


def test_source_snapshot_ids_must_be_unique(tmp_path):
    snapshots = [
        {
            "snapshot_id": "same",
            "source_kind": "CANONICAL_PROPERTY_ROSTER",
            "authority": "authority",
            "captured_at": "2026-09-18T00:00:00Z",
            "sha256": "a" * 64,
        },
        {
            "snapshot_id": "same",
            "source_kind": "COUNTY_PARCEL",
            "authority": "authority",
            "captured_at": "2026-09-18T00:00:00Z",
            "sha256": "b" * 64,
        },
    ]
    path = write_manifest(
        tmp_path,
        [member("STH-516010270", lineage_refs=["same"])],
        snapshots=snapshots,
    )
    with pytest.raises(ValueError, match="duplicate source snapshot id"):
        loader().load(path)
