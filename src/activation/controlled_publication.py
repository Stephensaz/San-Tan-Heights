from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
from typing import Iterable, Mapping

import yaml


ALLOWED_TIERS = ("AGENT", "SELLER", "PUBLIC")
STAGE_ORDER = ("COHORT_25", "COHORT_100", "COHORT_500", "REMAINING_FLEET")


@dataclass(frozen=True)
class PublicationVariant:
    canonical_property_id: str
    output_tier: str
    report_state_key: str
    passport_fingerprint: str
    report_fingerprint: str
    publication_state: str
    tier_eligible: bool
    quarantined: bool
    stale_current_displayed: bool


@dataclass(frozen=True)
class FrozenPublicationCohort:
    cohort_code: str
    candidate_fingerprint: str
    property_ids: tuple[str, ...]
    allowed_tiers: tuple[str, ...]
    membership_fingerprint: str


@dataclass(frozen=True)
class PublicationPointer:
    canonical_property_id: str
    output_tier: str
    report_state_key: str | None
    report_fingerprint: str | None


@dataclass(frozen=True)
class PublicationMutation:
    canonical_property_id: str
    output_tier: str
    previous_report_state_key: str | None
    next_report_state_key: str
    next_report_fingerprint: str
    mutation_fingerprint: str


@dataclass(frozen=True)
class PublicationBatchResult:
    cohort_code: str
    mutations: tuple[PublicationMutation, ...]
    publication_fingerprint: str


def _canonical_hash(payload: object) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return sha256(encoded).hexdigest()


def load_publication_policy(path: str | Path) -> dict:
    policy = yaml.safe_load(Path(path).read_text())
    if policy.get("publication_policy_id") != "STH-M9-010-CONTROLLED-PUBLICATION-v1.0":
        raise ValueError("unexpected M9-010 publication policy id")
    if str(policy.get("version")) != "1.0.0" or policy.get("status") != "FROZEN":
        raise ValueError("M9-010 publication policy must be FROZEN v1.0.0")
    if tuple(policy.get("stage_order") or ()) != STAGE_ORDER:
        raise ValueError("M9-010 stage order drift")
    if tuple(policy.get("allowed_tiers") or ()) != ALLOWED_TIERS:
        raise ValueError("M9-010 allowed tier drift")
    return policy


def validate_variant_for_publication(variant: PublicationVariant) -> None:
    if variant.output_tier not in ALLOWED_TIERS:
        raise ValueError("unsupported publication tier")
    if not variant.canonical_property_id.startswith("STH-"):
        raise ValueError("unexpected canonical property id")
    if not variant.tier_eligible:
        raise ValueError("variant is not tier eligible")
    if variant.quarantined:
        raise ValueError("quarantined content cannot publish")
    if variant.stale_current_displayed:
        raise ValueError("stale current content cannot publish")
    if variant.publication_state not in {"MATERIALIZED_NOT_PUBLISHED", "PUBLISHED"}:
        raise ValueError("unsupported publication state")
    if len(variant.report_state_key) != 64 or len(variant.passport_fingerprint) != 64 or len(variant.report_fingerprint) != 64:
        raise ValueError("publication fingerprints must be sha256")


def freeze_publication_cohort(
    *,
    cohort_code: str,
    candidate_fingerprint: str,
    eligible_property_ids: Iterable[str],
    prior_cohort_property_ids: Iterable[str] = (),
    policy: Mapping[str, object],
) -> FrozenPublicationCohort:
    if cohort_code not in STAGE_ORDER:
        raise ValueError("unknown publication cohort")
    if len(candidate_fingerprint) != 64:
        raise ValueError("candidate fingerprint must be sha256")

    configured = policy["stages"][cohort_code]
    size = configured["property_count"]
    prior_required = configured.get("prior_stage")

    prior = tuple(sorted(set(prior_cohort_property_ids)))
    eligible_raw = tuple(eligible_property_ids)
    if len(set(eligible_raw)) != len(eligible_raw):
        raise ValueError("duplicate eligible property ids")
    eligible = tuple(sorted(eligible_raw))
    if any(not p.startswith("STH-") for p in eligible):
        raise ValueError("invalid canonical property id in eligibility set")

    if prior_required and not prior:
        raise ValueError("prior cohort evidence is required")
    remaining = tuple(p for p in eligible if p not in set(prior))

    if size == "ALL_REMAINING":
        selected = remaining
    else:
        selected = remaining[: int(size)]
        if len(selected) != int(size):
            raise ValueError("insufficient eligible properties for exact cohort")

    if not selected:
        raise ValueError("publication cohort cannot be empty")

    payload = {
        "cohort_code": cohort_code,
        "candidate_fingerprint": candidate_fingerprint,
        "property_ids": list(selected),
        "allowed_tiers": list(ALLOWED_TIERS),
    }
    return FrozenPublicationCohort(
        cohort_code=cohort_code,
        candidate_fingerprint=candidate_fingerprint,
        property_ids=selected,
        allowed_tiers=ALLOWED_TIERS,
        membership_fingerprint=_canonical_hash(payload),
    )


def build_publication_batch(
    *,
    cohort: FrozenPublicationCohort,
    variants: Iterable[PublicationVariant],
    current_pointers: Iterable[PublicationPointer],
) -> PublicationBatchResult:
    by_key = {(v.canonical_property_id, v.output_tier): v for v in variants}
    pointer_map = {(p.canonical_property_id, p.output_tier): p for p in current_pointers}
    mutations: list[PublicationMutation] = []

    expected_keys = {(pid, tier) for pid in cohort.property_ids for tier in cohort.allowed_tiers}
    missing = sorted(expected_keys - set(by_key))
    if missing:
        raise ValueError(f"publication variants missing for cohort: {missing[:3]}")

    extra = [k for k in by_key if k[0] not in set(cohort.property_ids)]
    if extra:
        raise ValueError("publication batch contains property outside frozen cohort")

    for pid in cohort.property_ids:
        for tier in cohort.allowed_tiers:
            variant = by_key[(pid, tier)]
            validate_variant_for_publication(variant)
            pointer = pointer_map.get((pid, tier))
            payload = {
                "canonical_property_id": pid,
                "output_tier": tier,
                "previous_report_state_key": pointer.report_state_key if pointer else None,
                "next_report_state_key": variant.report_state_key,
                "next_report_fingerprint": variant.report_fingerprint,
            }
            mutations.append(
                PublicationMutation(
                    canonical_property_id=pid,
                    output_tier=tier,
                    previous_report_state_key=pointer.report_state_key if pointer else None,
                    next_report_state_key=variant.report_state_key,
                    next_report_fingerprint=variant.report_fingerprint,
                    mutation_fingerprint=_canonical_hash(payload),
                )
            )

    batch_payload = {
        "cohort_code": cohort.cohort_code,
        "candidate_fingerprint": cohort.candidate_fingerprint,
        "membership_fingerprint": cohort.membership_fingerprint,
        "mutation_fingerprints": [m.mutation_fingerprint for m in mutations],
    }
    return PublicationBatchResult(
        cohort_code=cohort.cohort_code,
        mutations=tuple(mutations),
        publication_fingerprint=_canonical_hash(batch_payload),
    )


def apply_pointer_batch(
    *,
    batch: PublicationBatchResult,
    current_pointers: Iterable[PublicationPointer],
) -> tuple[PublicationPointer, ...]:
    pointers = {(p.canonical_property_id, p.output_tier): p for p in current_pointers}
    for mutation in batch.mutations:
        key = (mutation.canonical_property_id, mutation.output_tier)
        current = pointers.get(key)
        current_key = current.report_state_key if current else None
        if current_key != mutation.previous_report_state_key:
            raise ValueError("publication pointer changed since batch was built")
        pointers[key] = PublicationPointer(
            canonical_property_id=mutation.canonical_property_id,
            output_tier=mutation.output_tier,
            report_state_key=mutation.next_report_state_key,
            report_fingerprint=mutation.next_report_fingerprint,
        )
    return tuple(sorted(pointers.values(), key=lambda p: (p.canonical_property_id, p.output_tier)))


def rollback_pointer_batch(
    *,
    before: Iterable[PublicationPointer],
    after: Iterable[PublicationPointer],
    batch: PublicationBatchResult,
) -> tuple[PublicationPointer, ...]:
    before_map = {(p.canonical_property_id, p.output_tier): p for p in before}
    after_map = {(p.canonical_property_id, p.output_tier): p for p in after}
    for mutation in batch.mutations:
        key = (mutation.canonical_property_id, mutation.output_tier)
        current = after_map.get(key)
        if current is None or current.report_state_key != mutation.next_report_state_key:
            raise ValueError("rollback target no longer matches publication batch")
        if key in before_map:
            after_map[key] = before_map[key]
        else:
            after_map.pop(key)
    return tuple(sorted(after_map.values(), key=lambda p: (p.canonical_property_id, p.output_tier)))


def validate_m9_010_repository_binding(root: str | Path = ".") -> str:
    root = Path(root)
    m9_009 = json.loads((root / "certification-evidence/m9-009/full-corpus-qa-v1.0.json").read_text())
    rollout = yaml.safe_load((root / "registries/production-certification/progressive-rollout-policy.yaml").read_text())
    manual = yaml.safe_load((root / "registries/production-certification/manual-publication-policy.yaml").read_text())
    reports = yaml.safe_load((root / "registries/activation/m9-007-report-materialization-v1.0.yaml").read_text())
    policy = load_publication_policy(root / "registries/activation/m9-010-controlled-publication-v1.0.yaml")

    if m9_009.get("status") != "ACCEPTED":
        raise ValueError("M9-009 must be accepted before M9-010")
    if rollout.get("status") != "LOCKED" or manual.get("status") != "LOCKED":
        raise ValueError("M7 rollout/publication controls are not locked")
    if tuple(rollout.get("allowed_variants") or ()) != ALLOWED_TIERS:
        raise ValueError("M7/M9 tier contract mismatch")
    if manual.get("default_mode") != "MANUAL":
        raise ValueError("M7 manual publication default weakened")
    if reports["publication_state"]["public_delivery_activated"] is not False:
        raise ValueError("publication already activated before M9-010")
    if reports["publication_state"]["physical_delivery_activated"] is not False:
        raise ValueError("physical delivery already activated before M9-010")
    if int(m9_009["defects"]["tier_leakage_violations"]) != 0:
        raise ValueError("M9-009 tier leakage prevents publication")
    if int(m9_009["defects"]["unauthorized_publications"]) != 0:
        raise ValueError("M9-009 unauthorized publication defect")
    if int(m9_009["defects"]["waivers"]) != 0:
        raise ValueError("M9-009 waivers prohibit publication")

    payload = {
        "m9_009_qa_fingerprint": m9_009["qa_fingerprint"],
        "m9_007_report_fingerprint": reports["artifact"]["aggregate_report_materialization_fingerprint"],
        "m7_rollout_policy_version": rollout["registry_version"],
        "m7_manual_publication_policy_version": manual["policy_version"],
        "m9_010_policy_version": policy["version"],
        "stage_order": policy["stage_order"],
    }
    return _canonical_hash(payload)
