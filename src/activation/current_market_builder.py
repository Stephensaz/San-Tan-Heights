from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from hashlib import sha256
import csv
from pathlib import Path

import yaml


@dataclass(frozen=True)
class CurrentContextAudit:
    corpus_members: int
    available: int
    unavailable: int
    unavailable_property_ids: tuple[str, ...]
    snapshot_date: str
    snapshot_age_days: int
    property_context_sha256: str
    builder_rows: int
    expired_builder_offer_terms: int
    builder_context_sha256: str


def _rows(path: str | Path) -> list[dict[str, str]]:
    raw = Path(path).read_bytes()
    return list(csv.DictReader(raw.decode("utf-8-sig").splitlines()))


def _sha(path: str | Path) -> str:
    return sha256(Path(path).read_bytes()).hexdigest()


def audit_current_context(
    registry_path: str | Path,
    property_context_path: str | Path,
    builder_context_path: str | Path,
) -> CurrentContextAudit:
    registry = yaml.safe_load(Path(registry_path).read_text())
    if registry.get("current_context_registry_id") != "STH-M9-005-CURRENT-MARKET-BUILDER-v1.0":
        raise ValueError("unexpected M9-005 registry id")
    if str(registry.get("version")) != "1.0.0" or registry.get("status") != "FROZEN":
        raise ValueError("M9-005 registry must be FROZEN v1.0.0")

    evaluation_date = date.fromisoformat(str(registry["evaluation_date"]))
    freshness = registry["freshness_policy"]
    max_age = int(freshness["snapshot_max_age_days"])

    prop = _rows(property_context_path)
    builder = _rows(builder_context_path)

    if len({r["canonical_property_id"] for r in prop}) != len(prop):
        raise ValueError("duplicate canonical property in M9-005 context")
    if len({r["county_parcelid"] for r in prop}) != len(prop):
        raise ValueError("duplicate ParcelID in M9-005 context")

    available = []
    unavailable = []
    snapshot_dates = set()
    ages = set()

    for row in prop:
        status = row["current_context_status"]
        snapshot_date = date.fromisoformat(row["snapshot_date"])
        expected_age = (evaluation_date - snapshot_date).days
        if int(row["snapshot_age_days"]) != expected_age:
            raise ValueError(f"{row['canonical_property_id']}: snapshot age mismatch")
        if expected_age < 0:
            raise ValueError(f"{row['canonical_property_id']}: future snapshot date")
        if expected_age <= max_age:
            expected_freshness = freshness["freshness_state_within_cadence"]
        else:
            expected_freshness = "STALE"
        if row["snapshot_freshness_state"] != expected_freshness:
            raise ValueError(f"{row['canonical_property_id']}: freshness state mismatch")

        snapshot_dates.add(row["snapshot_date"])
        ages.add(expected_age)

        count_fields = (
            "currently_available_close_substitute_property_count",
            "currently_available_strict_substitute_property_count",
            "currently_marketed_under_contract_close_substitute_property_count",
        )
        if status == "AVAILABLE":
            if any(row[field] == "" for field in count_fields):
                raise ValueError(f"{row['canonical_property_id']}: available context missing counts")
            if row["source_qa_status"] != "PASS":
                raise ValueError(f"{row['canonical_property_id']}: available context not QA PASS")
            if row["unavailable_reason"]:
                raise ValueError(f"{row['canonical_property_id']}: available context carries unavailable reason")
            available.append(row)
        elif status == "UNAVAILABLE":
            if any(row[field] != "" for field in count_fields):
                raise ValueError(f"{row['canonical_property_id']}: unavailable context contains inferred counts")
            if not row["unavailable_reason"]:
                raise ValueError(f"{row['canonical_property_id']}: unavailable context missing reason")
            unavailable.append(row)
        else:
            raise ValueError(f"{row['canonical_property_id']}: unsupported current context status")

    if len(snapshot_dates) != 1 or len(ages) != 1:
        raise ValueError("M9-005 property context contains mixed snapshot dates/ages")

    if len({r["builder_context_id"] for r in builder}) != len(builder):
        raise ValueError("duplicate M9-005 builder context id")

    expired = 0
    for row in builder:
        source_date = date.fromisoformat(row["source_as_of"])
        expected_age = (evaluation_date - source_date).days
        if int(row["snapshot_age_days"]) != expected_age:
            raise ValueError(f"{row['builder_context_id']}: builder snapshot age mismatch")
        expected_freshness = freshness["freshness_state_within_cadence"] if expected_age <= max_age else "STALE"
        if row["snapshot_freshness_state"] != expected_freshness:
            raise ValueError(f"{row['builder_context_id']}: builder freshness state mismatch")

        end = row["explicit_offer_end_date"]
        validity = row["offer_validity_state"]
        if end:
            end_date = date.fromisoformat(end)
            expected_validity = (
                "EXPIRED_BY_EXPLICIT_SOURCE_DATE"
                if evaluation_date > end_date
                else "VALID_BY_EXPLICIT_SOURCE_DATE"
            )
            if validity != expected_validity:
                raise ValueError(f"{row['builder_context_id']}: explicit offer validity mismatch")
            if expected_validity == "EXPIRED_BY_EXPLICIT_SOURCE_DATE":
                expired += 1
        elif validity != "NO_EXPLICIT_END_DATE":
            raise ValueError(f"{row['builder_context_id']}: offer validity asserted without explicit end date")

    p = registry["property_population"]
    b = registry["builder_context"]
    artifacts = registry["artifacts"]

    audit = CurrentContextAudit(
        corpus_members=len(prop),
        available=len(available),
        unavailable=len(unavailable),
        unavailable_property_ids=tuple(sorted(r["canonical_property_id"] for r in unavailable)),
        snapshot_date=next(iter(snapshot_dates)),
        snapshot_age_days=next(iter(ages)),
        property_context_sha256=_sha(property_context_path),
        builder_rows=len(builder),
        expired_builder_offer_terms=expired,
        builder_context_sha256=_sha(builder_context_path),
    )

    checks = (
        ("corpus_members", p["corpus_members"], audit.corpus_members),
        ("current_context_available", p["current_context_available"], audit.available),
        ("current_context_unavailable", p["current_context_unavailable"], audit.unavailable),
        ("snapshot_age_days", p["snapshot_age_days_at_evaluation"], audit.snapshot_age_days),
        ("builder_alternatives", b["alternatives"], audit.builder_rows),
        ("expired_builder_offer_terms", b["explicit_offer_end_dates"]["expired_as_of_evaluation"], audit.expired_builder_offer_terms),
    )
    for name, expected, actual in checks:
        if expected != actual:
            raise ValueError(f"M9-005 count mismatch for {name}: expected={expected}, actual={actual}")

    if tuple(p["unavailable_property_ids"]) != audit.unavailable_property_ids:
        raise ValueError("M9-005 unavailable property set mismatch")
    for property_id in audit.unavailable_property_ids:
        if p["unavailable_reason"].get(property_id) != "UPSTREAM_SPATIAL_FRONTAGE_UNRESOLVED":
            raise ValueError("M9-005 unavailable reason drift")

    if artifacts["property_context"]["raw_sha256"] != audit.property_context_sha256:
        raise ValueError("M9-005 property context SHA-256 mismatch")
    if artifacts["builder_context"]["raw_sha256"] != audit.builder_context_sha256:
        raise ValueError("M9-005 builder context SHA-256 mismatch")

    governance = registry["governance"]
    required_true = (
        "historical_layer_immutable",
        "preserve_source_values",
        "preserve_source_dates",
        "preserve_source_qa_states",
        "stale_or_unavailable_states_explicit",
        "expired_offer_terms_not_carried_forward_as_current",
        "property_specific_builder_substitution_inference_prohibited",
        "new_pricing_conclusions_prohibited",
        "new_value_opinions_prohibited",
        "current_market_refresh_outside_frozen_snapshot_prohibited",
        "report_generation_prohibited",
        "publication_prohibited",
    )
    if any(governance.get(key) is not True for key in required_true):
        raise ValueError("M9-005 governance weakened")

    return audit
