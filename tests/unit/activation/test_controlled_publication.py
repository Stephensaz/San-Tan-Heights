from copy import deepcopy

import pytest

from src.activation.controlled_publication import (
    PublicationPointer,
    PublicationVariant,
    apply_pointer_batch,
    build_publication_batch,
    freeze_publication_cohort,
    load_publication_policy,
    rollback_pointer_batch,
    validate_m9_010_repository_binding,
)


POLICY_PATH = "registries/activation/m9-010-controlled-publication-v1.0.yaml"


def policy():
    return load_publication_policy(POLICY_PATH)


def ids(n):
    return [f"STH-{i:04d}" for i in range(1, n + 1)]


def variants(property_ids):
    rows = []
    for pid in property_ids:
        for tier in ("AGENT", "SELLER", "PUBLIC"):
            rows.append(PublicationVariant(
                canonical_property_id=pid,
                output_tier=tier,
                report_state_key=("a" if tier == "AGENT" else "b" if tier == "SELLER" else "c") * 64,
                passport_fingerprint="d" * 64,
                report_fingerprint=("1" if tier == "AGENT" else "2" if tier == "SELLER" else "3") * 64,
                publication_state="MATERIALIZED_NOT_PUBLISHED",
                tier_eligible=True,
                quarantined=False,
                stale_current_displayed=False,
            ))
    return rows


def test_repository_binding_to_m7_and_m9_009_passes():
    fp = validate_m9_010_repository_binding(".")
    assert len(fp) == 64


def test_cohort_25_is_exact_and_deterministic():
    eligible = list(reversed(ids(40)))
    a = freeze_publication_cohort(
        cohort_code="COHORT_25",
        candidate_fingerprint="f" * 64,
        eligible_property_ids=eligible,
        policy=policy(),
    )
    b = freeze_publication_cohort(
        cohort_code="COHORT_25",
        candidate_fingerprint="f" * 64,
        eligible_property_ids=eligible,
        policy=policy(),
    )
    assert len(a.property_ids) == 25
    assert a.property_ids == tuple(ids(25))
    assert a.membership_fingerprint == b.membership_fingerprint


def test_later_cohort_excludes_prior_members():
    eligible = ids(150)
    first = freeze_publication_cohort(
        cohort_code="COHORT_25",
        candidate_fingerprint="f" * 64,
        eligible_property_ids=eligible,
        policy=policy(),
    )
    second = freeze_publication_cohort(
        cohort_code="COHORT_100",
        candidate_fingerprint="f" * 64,
        eligible_property_ids=eligible,
        prior_cohort_property_ids=first.property_ids,
        policy=policy(),
    )
    assert len(second.property_ids) == 100
    assert not set(first.property_ids) & set(second.property_ids)


def test_batch_requires_all_three_safe_tiers():
    cohort = freeze_publication_cohort(
        cohort_code="COHORT_25",
        candidate_fingerprint="f" * 64,
        eligible_property_ids=ids(25),
        policy=policy(),
    )
    rows = variants(cohort.property_ids)
    rows.pop()
    with pytest.raises(ValueError, match="variants missing"):
        build_publication_batch(cohort=cohort, variants=rows, current_pointers=[])


def test_quarantined_variant_cannot_publish():
    cohort = freeze_publication_cohort(
        cohort_code="COHORT_25",
        candidate_fingerprint="f" * 64,
        eligible_property_ids=ids(25),
        policy=policy(),
    )
    rows = variants(cohort.property_ids)
    bad = rows[0]
    rows[0] = PublicationVariant(**{**bad.__dict__, "quarantined": True})
    with pytest.raises(ValueError, match="quarantined content"):
        build_publication_batch(cohort=cohort, variants=rows, current_pointers=[])


def test_stale_current_variant_cannot_publish():
    cohort = freeze_publication_cohort(
        cohort_code="COHORT_25",
        candidate_fingerprint="f" * 64,
        eligible_property_ids=ids(25),
        policy=policy(),
    )
    rows = variants(cohort.property_ids)
    bad = rows[0]
    rows[0] = PublicationVariant(**{**bad.__dict__, "stale_current_displayed": True})
    with pytest.raises(ValueError, match="stale current content"):
        build_publication_batch(cohort=cohort, variants=rows, current_pointers=[])


def test_pointer_batch_is_compare_and_swap_and_rollback_safe():
    cohort = freeze_publication_cohort(
        cohort_code="COHORT_25",
        candidate_fingerprint="f" * 64,
        eligible_property_ids=ids(25),
        policy=policy(),
    )
    rows = variants(cohort.property_ids)
    before = []
    batch = build_publication_batch(cohort=cohort, variants=rows, current_pointers=before)
    after = apply_pointer_batch(batch=batch, current_pointers=before)
    assert len(after) == 75
    restored = rollback_pointer_batch(before=before, after=after, batch=batch)
    assert restored == ()


def test_pointer_change_after_batch_build_fails_closed():
    cohort = freeze_publication_cohort(
        cohort_code="COHORT_25",
        candidate_fingerprint="f" * 64,
        eligible_property_ids=ids(25),
        policy=policy(),
    )
    rows = variants(cohort.property_ids)
    before = []
    batch = build_publication_batch(cohort=cohort, variants=rows, current_pointers=before)
    raced = [PublicationPointer(
        canonical_property_id="STH-0001",
        output_tier="AGENT",
        report_state_key="9" * 64,
        report_fingerprint="8" * 64,
    )]
    with pytest.raises(ValueError, match="pointer changed"):
        apply_pointer_batch(batch=batch, current_pointers=raced)


def test_duplicate_eligible_property_ids_fail():
    with pytest.raises(ValueError, match="duplicate eligible"):
        freeze_publication_cohort(
            cohort_code="COHORT_25",
            candidate_fingerprint="f" * 64,
            eligible_property_ids=ids(25) + ["STH-0001"],
            policy=policy(),
        )
