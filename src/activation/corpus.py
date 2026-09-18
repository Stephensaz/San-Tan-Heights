from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from hashlib import sha256
import json
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping

import jsonschema

from src.shared.canonical_json import canonical_json


class AdmissionState(str, Enum):
    ADMITTED = "ADMITTED"
    QUARANTINED = "QUARANTINED"
    EXCLUDED_WITH_GOVERNED_REASON = "EXCLUDED_WITH_GOVERNED_REASON"


class QuarantineReason(str, Enum):
    IDENTITY_UNRESOLVED = "IDENTITY_UNRESOLVED"
    DUPLICATE_IDENTITY = "DUPLICATE_IDENTITY"
    MISSING_LINEAGE = "MISSING_LINEAGE"
    PHASE_UNRESOLVED = "PHASE_UNRESOLVED"
    SPATIAL_UNRESOLVED = "SPATIAL_UNRESOLVED"
    SOURCE_CONFLICT = "SOURCE_CONFLICT"
    SOURCE_SNAPSHOT_UNAPPROVED = "SOURCE_SNAPSHOT_UNAPPROVED"
    OTHER_GOVERNED = "OTHER_GOVERNED"


class ExclusionReason(str, Enum):
    NON_RESIDENTIAL_OR_COMMON_AREA = "NON_RESIDENTIAL_OR_COMMON_AREA"
    OUTSIDE_CANONICAL_BOUNDARY = "OUTSIDE_CANONICAL_BOUNDARY"
    RETIRED_OR_SUPERSEDED_PARCEL = "RETIRED_OR_SUPERSEDED_PARCEL"
    DUPLICATE_SOURCE_RECORD = "DUPLICATE_SOURCE_RECORD"
    OTHER_GOVERNED = "OTHER_GOVERNED"


@dataclass(frozen=True)
class SourceSnapshot:
    snapshot_id: str
    source_kind: str
    authority: str
    captured_at: str
    sha256: str


@dataclass(frozen=True)
class CorpusMember:
    canonical_property_id: str
    county_parcelid: str | None
    admission_state: AdmissionState
    quarantine_reasons: tuple[QuarantineReason, ...]
    exclusion_reason: ExclusionReason | None
    lineage_refs: tuple[str, ...]


@dataclass(frozen=True)
class ProductionCorpusManifest:
    manifest_id: str
    version: str
    status: str
    community_id: str
    declared_total: int
    source_snapshots: tuple[SourceSnapshot, ...]
    members: tuple[CorpusMember, ...]
    fingerprint: str
    state_counts: Mapping[str, int]

    def canonical_payload(self) -> dict[str, object]:
        return {
            "manifest_id": self.manifest_id,
            "version": self.version,
            "status": self.status,
            "community_id": self.community_id,
            "declared_total": self.declared_total,
            "source_snapshots": [
                {
                    "snapshot_id": item.snapshot_id,
                    "source_kind": item.source_kind,
                    "authority": item.authority,
                    "captured_at": item.captured_at,
                    "sha256": item.sha256,
                }
                for item in self.source_snapshots
            ],
            "members": [
                {
                    "canonical_property_id": item.canonical_property_id,
                    "county_parcelid": item.county_parcelid,
                    "admission_state": item.admission_state.value,
                    "quarantine_reasons": [reason.value for reason in item.quarantine_reasons],
                    "exclusion_reason": None if item.exclusion_reason is None else item.exclusion_reason.value,
                    "lineage_refs": list(item.lineage_refs),
                }
                for item in self.members
            ],
        }


class ProductionCorpusManifestLoader:
    def __init__(self, schema_path: str | Path) -> None:
        self.schema = json.loads(Path(schema_path).read_text())

    def load(self, path: str | Path, *, require_frozen: bool = True) -> ProductionCorpusManifest:
        raw = json.loads(Path(path).read_text())
        jsonschema.validate(raw, self.schema)

        if require_frozen and raw["status"] != "FROZEN":
            raise ValueError("production corpus manifest must be FROZEN")

        snapshots_raw = tuple(raw["source_snapshots"])
        snapshot_ids = tuple(item["snapshot_id"] for item in snapshots_raw)
        if len(set(snapshot_ids)) != len(snapshot_ids):
            raise ValueError("duplicate source snapshot id")

        members_raw = tuple(raw["members"])
        if raw["declared_total"] != len(members_raw):
            raise ValueError("declared_total does not match corpus membership")

        property_ids = tuple(item["canonical_property_id"] for item in members_raw)
        if len(set(property_ids)) != len(property_ids):
            raise ValueError("duplicate canonical property identity")

        snapshot_id_set = set(snapshot_ids)
        members: list[CorpusMember] = []
        counts = {state.value: 0 for state in AdmissionState}

        for item in members_raw:
            state = AdmissionState(item["admission_state"])
            lineage_refs = tuple(item["lineage_refs"])
            if set(lineage_refs) - snapshot_id_set:
                raise ValueError(
                    f"{item['canonical_property_id']}: lineage references unknown source snapshot"
                )

            quarantine_reasons = tuple(
                QuarantineReason(reason) for reason in item.get("quarantine_reasons", ())
            )
            exclusion_raw = item.get("exclusion_reason")
            exclusion_reason = None if exclusion_raw is None else ExclusionReason(exclusion_raw)

            if state is AdmissionState.ADMITTED:
                if quarantine_reasons or exclusion_reason is not None:
                    raise ValueError(
                        f"{item['canonical_property_id']}: admitted record carries exception reason"
                    )
            elif state is AdmissionState.QUARANTINED:
                if not quarantine_reasons or exclusion_reason is not None:
                    raise ValueError(
                        f"{item['canonical_property_id']}: quarantined record lacks governed quarantine reason"
                    )
            else:
                if exclusion_reason is None or quarantine_reasons:
                    raise ValueError(
                        f"{item['canonical_property_id']}: excluded record lacks governed exclusion reason"
                    )

            members.append(
                CorpusMember(
                    canonical_property_id=item["canonical_property_id"],
                    county_parcelid=item.get("county_parcelid"),
                    admission_state=state,
                    quarantine_reasons=quarantine_reasons,
                    exclusion_reason=exclusion_reason,
                    lineage_refs=lineage_refs,
                )
            )
            counts[state.value] += 1

        snapshots = tuple(
            SourceSnapshot(
                snapshot_id=item["snapshot_id"],
                source_kind=item["source_kind"],
                authority=item["authority"],
                captured_at=item["captured_at"],
                sha256=item["sha256"],
            )
            for item in snapshots_raw
        )

        ordered_members = tuple(sorted(members, key=lambda item: item.canonical_property_id))
        ordered_snapshots = tuple(sorted(snapshots, key=lambda item: item.snapshot_id))
        canonical = {
            "manifest_id": raw["manifest_id"],
            "version": raw["version"],
            "status": raw["status"],
            "community_id": raw["community_id"],
            "declared_total": raw["declared_total"],
            "source_snapshots": [
                {
                    "snapshot_id": item.snapshot_id,
                    "source_kind": item.source_kind,
                    "authority": item.authority,
                    "captured_at": item.captured_at,
                    "sha256": item.sha256,
                }
                for item in ordered_snapshots
            ],
            "members": [
                {
                    "canonical_property_id": item.canonical_property_id,
                    "county_parcelid": item.county_parcelid,
                    "admission_state": item.admission_state.value,
                    "quarantine_reasons": [reason.value for reason in sorted(item.quarantine_reasons, key=lambda r: r.value)],
                    "exclusion_reason": None if item.exclusion_reason is None else item.exclusion_reason.value,
                    "lineage_refs": sorted(item.lineage_refs),
                }
                for item in ordered_members
            ],
        }
        fingerprint = sha256(canonical_json(canonical).encode("utf-8")).hexdigest()

        return ProductionCorpusManifest(
            manifest_id=raw["manifest_id"],
            version=raw["version"],
            status=raw["status"],
            community_id=raw["community_id"],
            declared_total=raw["declared_total"],
            source_snapshots=ordered_snapshots,
            members=ordered_members,
            fingerprint=fingerprint,
            state_counts=MappingProxyType(dict(sorted(counts.items()))),
        )
