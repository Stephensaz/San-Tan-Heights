from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import csv
from pathlib import Path

import yaml


@dataclass(frozen=True)
class HistoricalPopulationAudit:
    corpus_members: int
    history_available_properties: int
    no_history_properties: int
    canonical_listing_records: int
    availability_windows: int
    replay_anchors: int
    legacy_bound_episodes: int
    legacy_unresolved_episodes: int
    property_population_sha256: str
    legacy_bridge_sha256: str


def _rows(path: str | Path) -> list[dict[str, str]]:
    raw = Path(path).read_bytes()
    return list(csv.DictReader(raw.decode("utf-8-sig").splitlines()))


def _sha(path: str | Path) -> str:
    return sha256(Path(path).read_bytes()).hexdigest()


def audit_historical_population(
    registry_path: str | Path,
    property_population_path: str | Path,
    legacy_bridge_path: str | Path,
) -> HistoricalPopulationAudit:
    registry = yaml.safe_load(Path(registry_path).read_text())
    if registry.get("historical_population_registry_id") != "STH-M9-004-HISTORICAL-INTELLIGENCE-v1.0":
        raise ValueError("unexpected M9-004 registry id")
    if str(registry.get("version")) != "1.0.0" or registry.get("status") != "FROZEN":
        raise ValueError("M9-004 registry must be FROZEN v1.0.0")

    prop = _rows(property_population_path)
    bridge = _rows(legacy_bridge_path)

    if len({r["canonical_property_id"] for r in prop}) != len(prop):
        raise ValueError("duplicate property in M9-004 historical population")
    if len({r["county_parcelid"] for r in prop}) != len(prop):
        raise ValueError("duplicate ParcelID in M9-004 historical population")

    allowed_status = {"GOVERNED_HISTORY_AVAILABLE", "NO_GOVERNED_HISTORY"}
    if any(r["history_population_status"] not in allowed_status for r in prop):
        raise ValueError("unsupported M9-004 property history status")

    available = [r for r in prop if r["history_population_status"] == "GOVERNED_HISTORY_AVAILABLE"]
    no_history = [r for r in prop if r["history_population_status"] == "NO_GOVERNED_HISTORY"]

    for row in prop:
        count = int(row["governed_listing_record_count"])
        if row["history_population_status"] == "GOVERNED_HISTORY_AVAILABLE":
            if count < 1 or row["verified_master_history_flag"] != "YES":
                raise ValueError(f"{row['canonical_property_id']}: invalid governed-history state")
            if row["timeline_scope_limit"] != "INITIAL_AVAILABLE_WINDOW_ONLY_WHEN_ELIGIBLE;NOT_COMPLETE_EVENT_HISTORY":
                raise ValueError(f"{row['canonical_property_id']}: timeline limitation drift")
        else:
            if count != 0 or row["verified_master_history_flag"] != "NO":
                raise ValueError(f"{row['canonical_property_id']}: invalid no-history state")
            if row["timeline_scope_limit"] != "NO_GOVERNED_HISTORY":
                raise ValueError(f"{row['canonical_property_id']}: no-history limitation drift")

        if count != int(row["verified_master_listing_count"]):
            raise ValueError(f"{row['canonical_property_id']}: listing count disagrees with verified master")

    if len({r["episode_id"] for r in bridge}) != len(bridge):
        raise ValueError("duplicate legacy episode identity")

    bound_bridge = [r for r in bridge if r["binding_status"] == "BOUND_CANONICAL_APN"]
    unresolved_bridge = [r for r in bridge if r["binding_status"] == "UNRESOLVED_NON_PROMOTED"]
    if len(bound_bridge) + len(unresolved_bridge) != len(bridge):
        raise ValueError("unsupported legacy episode binding status")
    if any(not r["canonical_property_id"] for r in bound_bridge):
        raise ValueError("bound legacy episode missing canonical property")
    if any(r["canonical_property_id"] for r in unresolved_bridge):
        raise ValueError("unresolved legacy episode was promoted")

    p = registry["population"]
    l = registry["legacy_episode_identity"]
    artifacts = registry["artifacts"]
    audit = HistoricalPopulationAudit(
        corpus_members=len(prop),
        history_available_properties=len(available),
        no_history_properties=len(no_history),
        canonical_listing_records=sum(int(r["governed_listing_record_count"]) for r in prop),
        availability_windows=sum(int(r["initial_availability_window_count"]) for r in prop),
        replay_anchors=sum(int(r["historical_replay_anchor_count"]) for r in prop),
        legacy_bound_episodes=len(bound_bridge),
        legacy_unresolved_episodes=len(unresolved_bridge),
        property_population_sha256=_sha(property_population_path),
        legacy_bridge_sha256=_sha(legacy_bridge_path),
    )

    checks = (
        ("corpus_members", p["corpus_members"], audit.corpus_members),
        ("history_available_properties", p["history_available_properties"], audit.history_available_properties),
        ("no_governed_history_properties", p["no_governed_history_properties"], audit.no_history_properties),
        ("canonical_listing_records_attached", p["canonical_listing_records_attached"], audit.canonical_listing_records),
        ("initial_availability_windows_attached", p["initial_availability_windows_attached"], audit.availability_windows),
        ("replay_anchors_attached", p["replay_anchors_attached"], audit.replay_anchors),
        ("legacy_bound", l["bound_to_canonical_property"], audit.legacy_bound_episodes),
        ("legacy_unresolved", l["unresolved_non_promoted"], audit.legacy_unresolved_episodes),
    )
    for name, expected, actual in checks:
        if expected != actual:
            raise ValueError(f"M9-004 count mismatch for {name}: expected={expected}, actual={actual}")

    if artifacts["property_population"]["raw_sha256"] != audit.property_population_sha256:
        raise ValueError("M9-004 property population SHA-256 mismatch")
    if artifacts["legacy_episode_bridge"]["raw_sha256"] != audit.legacy_bridge_sha256:
        raise ValueError("M9-004 legacy bridge SHA-256 mismatch")

    governance = registry["governance"]
    required_true = (
        "preserve_listing_identity",
        "preserve_legacy_episode_identity",
        "unresolved_history_non_promoted",
        "address_only_identity_substitution_prohibited",
        "new_episode_splitting_or_merging_prohibited",
        "new_price_interpretation_prohibited",
        "new_market_behavior_inference_prohibited",
        "recompute_analytical_studies_prohibited",
        "no_history_stays_explicit",
        "current_market_refresh_prohibited",
        "report_generation_prohibited",
        "publication_prohibited",
    )
    if any(governance.get(key) is not True for key in required_true):
        raise ValueError("M9-004 governance weakened")

    return audit
