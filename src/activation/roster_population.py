from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import csv
from pathlib import Path
from typing import Iterable

import yaml


@dataclass(frozen=True)
class ActivationRosterAudit:
    row_count: int
    unique_canonical_property_ids: int
    unique_county_parcelids: int
    additions_vs_source: int
    omissions_vs_source: int
    duplicate_canonical_property_ids: int
    duplicate_county_parcelids: int
    blank_lineage_fingerprints: int
    duplicate_lineage_fingerprints: int
    canonical_property_ids_sha256: str
    county_parcelids_sha256: str
    property_parcel_pairs_sha256: str
    raw_size_bytes: int
    raw_sha256: str


def _digest_lines(values: Iterable[str]) -> str:
    return sha256(("\n".join(values) + "\n").encode("utf-8")).hexdigest()


def _read_source_members(path: str | Path) -> tuple[tuple[str, str], ...]:
    raw = Path(path).read_bytes()
    rows = list(csv.DictReader(raw.decode("utf-8-sig").splitlines()))
    required = {"canonical_property_id", "county_parcelid"}
    if not rows or not required <= set(rows[0]):
        raise ValueError("source roster missing required identity columns")

    pairs: list[tuple[str, str]] = []
    for row in rows:
        property_id = row["canonical_property_id"].strip()
        parcel_id = row["county_parcelid"].strip()
        if not property_id or not parcel_id:
            raise ValueError("source roster contains blank identity")
        pairs.append((property_id, parcel_id))

    if len({p for p, _ in pairs}) != len(pairs):
        raise ValueError("source roster contains duplicate canonical property identity")
    if len({q for _, q in pairs}) != len(pairs):
        raise ValueError("source roster contains duplicate county parcel identity")
    return tuple(sorted(pairs))


def build_activation_roster(
    source_roster_path: str | Path,
    output_path: str | Path,
    *,
    m9_001_freeze_fingerprint: str,
) -> ActivationRosterAudit:
    if len(m9_001_freeze_fingerprint) != 64:
        raise ValueError("M9-001 freeze fingerprint must be lowercase SHA-256")

    source_pairs = _read_source_members(source_roster_path)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", newline="", encoding="utf-8") as handle:
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
        for property_id, parcel_id in source_pairs:
            lineage = sha256(
                f"{property_id}|{parcel_id}|{m9_001_freeze_fingerprint}".encode("utf-8")
            ).hexdigest()
            writer.writerow(
                {
                    "canonical_property_id": property_id,
                    "county_parcelid": parcel_id,
                    "source_freeze_fingerprint": m9_001_freeze_fingerprint,
                    "member_lineage_fingerprint": lineage,
                }
            )

    return audit_activation_roster(
        output_path,
        source_pairs=source_pairs,
        m9_001_freeze_fingerprint=m9_001_freeze_fingerprint,
    )


def audit_activation_roster(
    roster_path: str | Path,
    *,
    source_pairs: tuple[tuple[str, str], ...],
    m9_001_freeze_fingerprint: str,
) -> ActivationRosterAudit:
    path = Path(roster_path)
    raw = path.read_bytes()
    rows = list(csv.DictReader(raw.decode("utf-8").splitlines()))
    required = {
        "canonical_property_id",
        "county_parcelid",
        "source_freeze_fingerprint",
        "member_lineage_fingerprint",
    }
    if not rows or set(rows[0]) != required:
        raise ValueError("activation roster has unexpected schema")

    output_pairs: list[tuple[str, str]] = []
    lineage_values: list[str] = []
    for row in rows:
        property_id = row["canonical_property_id"].strip()
        parcel_id = row["county_parcelid"].strip()
        source_fingerprint = row["source_freeze_fingerprint"].strip()
        lineage = row["member_lineage_fingerprint"].strip()

        if source_fingerprint != m9_001_freeze_fingerprint:
            raise ValueError(f"{property_id}: M9-001 lineage fingerprint mismatch")
        expected_lineage = sha256(
            f"{property_id}|{parcel_id}|{m9_001_freeze_fingerprint}".encode("utf-8")
        ).hexdigest()
        if lineage != expected_lineage:
            raise ValueError(f"{property_id}: member lineage fingerprint mismatch")

        output_pairs.append((property_id, parcel_id))
        lineage_values.append(lineage)

    source_set = set(source_pairs)
    output_set = set(output_pairs)
    additions = output_set - source_set
    omissions = source_set - output_set
    property_ids = [p for p, _ in output_pairs]
    parcel_ids = [q for _, q in output_pairs]

    audit = ActivationRosterAudit(
        row_count=len(rows),
        unique_canonical_property_ids=len(set(property_ids)),
        unique_county_parcelids=len(set(parcel_ids)),
        additions_vs_source=len(additions),
        omissions_vs_source=len(omissions),
        duplicate_canonical_property_ids=len(property_ids) - len(set(property_ids)),
        duplicate_county_parcelids=len(parcel_ids) - len(set(parcel_ids)),
        blank_lineage_fingerprints=sum(not value for value in lineage_values),
        duplicate_lineage_fingerprints=len(lineage_values) - len(set(lineage_values)),
        canonical_property_ids_sha256=_digest_lines(sorted(property_ids)),
        county_parcelids_sha256=_digest_lines(sorted(parcel_ids)),
        property_parcel_pairs_sha256=_digest_lines(
            f"{property_id},{parcel_id}" for property_id, parcel_id in sorted(output_pairs)
        ),
        raw_size_bytes=len(raw),
        raw_sha256=sha256(raw).hexdigest(),
    )

    if audit.additions_vs_source or audit.omissions_vs_source:
        raise ValueError(
            f"activation membership mismatch: additions={audit.additions_vs_source}, "
            f"omissions={audit.omissions_vs_source}"
        )
    if audit.duplicate_canonical_property_ids:
        raise ValueError("duplicate canonical property identity in activation roster")
    if audit.duplicate_county_parcelids:
        raise ValueError("duplicate county parcel identity in activation roster")
    if audit.blank_lineage_fingerprints:
        raise ValueError("blank member lineage fingerprint")
    if audit.duplicate_lineage_fingerprints:
        raise ValueError("duplicate member lineage fingerprint")

    return audit


def validate_against_registry(
    registry_path: str | Path,
    roster_path: str | Path,
    source_roster_path: str | Path,
) -> ActivationRosterAudit:
    registry = yaml.safe_load(Path(registry_path).read_text())
    if registry.get("activation_roster_id") != "STH-M9-002-CANONICAL-ROSTER-v1.0":
        raise ValueError("unexpected M9-002 activation roster id")
    if str(registry.get("version")) != "1.0.0" or registry.get("status") != "FROZEN":
        raise ValueError("M9-002 activation roster registry must be FROZEN v1.0.0")

    freeze = registry["source"]["m9_001_freeze_fingerprint"]
    source_pairs = _read_source_members(source_roster_path)
    audit = audit_activation_roster(
        roster_path,
        source_pairs=source_pairs,
        m9_001_freeze_fingerprint=freeze,
    )
    artifact = registry["artifact"]
    population = registry["population"]

    checks = {
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
    }
    for key, value in checks.items():
        if population.get(key) != value:
            raise ValueError(f"M9-002 registry mismatch for {key}")

    if artifact["raw_size_bytes"] != audit.raw_size_bytes:
        raise ValueError("M9-002 artifact raw size mismatch")
    if artifact["raw_sha256"] != audit.raw_sha256:
        raise ValueError("M9-002 artifact SHA-256 mismatch")

    return audit
