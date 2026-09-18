from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import csv
from pathlib import Path
from types import MappingProxyType
from typing import Mapping

import yaml

from src.shared.canonical_json import canonical_json


@dataclass(frozen=True)
class ProductionCorpusFreeze:
    freeze_id: str
    version: str
    status: str
    community_id: str
    raw_size_bytes: int
    raw_sha256: str
    declared_total: int
    canonical_property_ids_sha256: str
    county_parcelids_sha256: str
    property_parcel_pairs_sha256: str
    admitted: int
    quarantined: int
    excluded: int
    fingerprint: str
    source: Mapping[str, object]


class ProductionCorpusFreezeValidator:
    """Validate the exact frozen M9-001 canonical roster bytes.

    The canonical CSV remains the single membership payload. This validator binds
    the exact bytes and the complete sorted identity sets without creating a
    competing duplicate roster.
    """

    def load_registry(self, path: str | Path) -> Mapping[str, object]:
        raw = yaml.safe_load(Path(path).read_text())
        if raw.get("production_corpus_freeze_id") != "STH-PRODUCTION-CORPUS-FREEZE-v1.0":
            raise ValueError("unexpected production corpus freeze id")
        if str(raw.get("version")) != "1.0.0" or raw.get("status") != "FROZEN":
            raise ValueError("production corpus freeze must be FROZEN v1.0.0")
        if raw.get("community_id") != "SAN_TAN_HEIGHTS":
            raise ValueError("unexpected production corpus community")
        return raw

    def validate(
        self,
        registry_path: str | Path,
        roster_path: str | Path,
    ) -> ProductionCorpusFreeze:
        registry = self.load_registry(registry_path)
        roster_path = Path(roster_path)
        raw_bytes = roster_path.read_bytes()

        expected = registry["canonical_roster"]
        if len(raw_bytes) != expected["raw_size_bytes"]:
            raise ValueError("canonical roster raw byte size mismatch")
        raw_hash = sha256(raw_bytes).hexdigest()
        if raw_hash != expected["raw_sha256"]:
            raise ValueError("canonical roster SHA-256 mismatch")

        text = raw_bytes.decode("utf-8-sig")
        rows = list(csv.DictReader(text.splitlines()))
        membership = registry["membership"]
        if len(rows) != membership["declared_total"]:
            raise ValueError("canonical roster row count mismatch")

        required_columns = {
            "canonical_property_id",
            "county_parcelid",
            "community_membership_status",
            "parcel_role",
            "canonical_master_version",
            "membership_change_policy",
        }
        if not rows or not required_columns <= set(rows[0]):
            raise ValueError("canonical roster missing required identity/governance columns")

        canonical_ids = [row["canonical_property_id"].strip() for row in rows]
        parcel_ids = [row["county_parcelid"].strip() for row in rows]

        if any(not value for value in canonical_ids):
            raise ValueError("blank canonical property identity")
        if any(not value for value in parcel_ids):
            raise ValueError("blank county parcel identity")
        if len(set(canonical_ids)) != len(canonical_ids):
            raise ValueError("duplicate canonical property identity")
        if len(set(parcel_ids)) != len(parcel_ids):
            raise ValueError("duplicate county parcel identity")

        if any(
            row["community_membership_status"] != "VERIFIED_RECORDED_SAN_TAN_HEIGHTS"
            for row in rows
        ):
            raise ValueError("non-verified community member present in frozen roster")
        if any(row["parcel_role"] != "RESIDENTIAL_LOT" for row in rows):
            raise ValueError("non-residential parcel present in frozen roster")
        if any(row["canonical_master_version"] != "1.0.0" for row in rows):
            raise ValueError("mixed canonical master versions in frozen roster")
        if any(
            row["membership_change_policy"] != "EVIDENCE_BACKED_CHANGE_EVENT_REQUIRED"
            for row in rows
        ):
            raise ValueError("membership change policy drift")

        canonical_ids_hash = sha256(
            ("\n".join(sorted(canonical_ids)) + "\n").encode("utf-8")
        ).hexdigest()
        parcel_ids_hash = sha256(
            ("\n".join(sorted(parcel_ids)) + "\n").encode("utf-8")
        ).hexdigest()
        pair_hash = sha256(
            (
                "\n".join(
                    f"{property_id},{parcel_id}"
                    for property_id, parcel_id in sorted(zip(canonical_ids, parcel_ids))
                )
                + "\n"
            ).encode("utf-8")
        ).hexdigest()

        if canonical_ids_hash != membership["canonical_property_ids_sha256"]:
            raise ValueError("canonical property membership digest mismatch")
        if parcel_ids_hash != membership["county_parcelids_sha256"]:
            raise ValueError("county parcel membership digest mismatch")
        if pair_hash != membership["canonical_property_id_to_parcelid_pairs_sha256"]:
            raise ValueError("canonical property-to-parcel pair digest mismatch")

        admission = registry["admission"]
        if admission["admitted"] != len(rows):
            raise ValueError("admitted count does not equal exact corpus membership")
        if admission["quarantined"] != 0 or admission["excluded_with_governed_reason"] != 0:
            raise ValueError("unexpected unresolved M9-001 admission exceptions")

        quality = registry["quality"]
        required_true = (
            "all_members_verified_recorded_san_tan_heights",
            "all_members_residential_lot",
            "all_members_master_version_1_0_0",
            "one_to_one_canonical_id_parcelid",
        )
        if any(quality.get(key) is not True for key in required_true):
            raise ValueError("production corpus quality assertion not satisfied")
        for key in (
            "duplicate_canonical_property_ids",
            "duplicate_county_parcelids",
            "missing_canonical_property_ids",
            "missing_county_parcelids",
        ):
            if quality.get(key) != 0:
                raise ValueError("production corpus quality defect count is nonzero")

        governance = registry["governance"]
        if governance.get("membership_payload_is_canonical_csv") is not True:
            raise ValueError("canonical CSV must remain the membership payload")
        if governance.get("duplicate_roster_prohibited") is not True:
            raise ValueError("duplicate roster must remain prohibited")
        if governance.get("membership_changes_require_evidence_backed_change_event") is not True:
            raise ValueError("membership changes must require governed evidence")
        if governance.get("all_members_accounted") is not True:
            raise ValueError("full membership accounting not asserted")
        if governance.get("conditional_go_prohibited") is not True:
            raise ValueError("conditional GO must remain prohibited")

        fingerprint_payload = {
            "freeze_id": registry["production_corpus_freeze_id"],
            "version": str(registry["version"]),
            "community_id": registry["community_id"],
            "raw_sha256": raw_hash,
            "raw_size_bytes": len(raw_bytes),
            "declared_total": len(rows),
            "canonical_property_ids_sha256": canonical_ids_hash,
            "county_parcelids_sha256": parcel_ids_hash,
            "property_parcel_pairs_sha256": pair_hash,
            "admitted": admission["admitted"],
            "quarantined": admission["quarantined"],
            "excluded": admission["excluded_with_governed_reason"],
        }
        freeze_fingerprint = sha256(
            canonical_json(fingerprint_payload).encode("utf-8")
        ).hexdigest()

        return ProductionCorpusFreeze(
            freeze_id=registry["production_corpus_freeze_id"],
            version=str(registry["version"]),
            status=registry["status"],
            community_id=registry["community_id"],
            raw_size_bytes=len(raw_bytes),
            raw_sha256=raw_hash,
            declared_total=len(rows),
            canonical_property_ids_sha256=canonical_ids_hash,
            county_parcelids_sha256=parcel_ids_hash,
            property_parcel_pairs_sha256=pair_hash,
            admitted=admission["admitted"],
            quarantined=admission["quarantined"],
            excluded=admission["excluded_with_governed_reason"],
            fingerprint=freeze_fingerprint,
            source=MappingProxyType(dict(expected)),
        )
