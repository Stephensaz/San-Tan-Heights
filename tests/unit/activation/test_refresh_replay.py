import pytest

from src.activation.controlled_publication import (
    PublicationPointer,
    PublicationVariant,
    build_publication_batch,
    freeze_publication_cohort,
    load_publication_policy,
)
from src.activation.refresh_replay import (
    ReplayRecord,
    audit_replay,
    load_replay_policy,
    validate_m9_011_repository_binding,
    validate_replay_failure_isolation,
    verify_publication_rollback,
)


def rp():
    return load_replay_policy("registries/activation/m9-011-refresh-replay-v1.0.yaml")


def pp():
    return load_publication_policy("registries/activation/m9-010-controlled-publication-v1.0.yaml")


def test_repository_binding_passes():
    fp = validate_m9_011_repository_binding(".")
    assert len(fp) == 64


def test_unchanged_records_remain_stable():
    rows = [
        ReplayRecord("STH-1", "AGENT", "a" * 64, "a" * 64, False),
        ReplayRecord("STH-1", "SELLER", "b" * 64, "b" * 64, False),
        ReplayRecord("STH-1", "PUBLIC", "c" * 64, "c" * 64, False),
    ]
    audit = audit_replay(rows, rp())
    assert audit.changed_unimpacted_records == 0
    assert audit.unchanged_records == 3


def test_governed_impacted_record_may_change():
    rows = [
        ReplayRecord("STH-1", "AGENT", "a" * 64, "d" * 64, True),
        ReplayRecord("STH-2", "AGENT", "b" * 64, "b" * 64, False),
    ]
    audit = audit_replay(rows, rp())
    assert audit.changed_impacted_records == 1
    assert audit.changed_unimpacted_records == 0


def test_unimpacted_fingerprint_drift_fails():
    rows = [ReplayRecord("STH-1", "PUBLIC", "a" * 64, "b" * 64, False)]
    with pytest.raises(ValueError, match="fingerprint drift"):
        audit_replay(rows, rp())


def test_failure_outside_impacted_scope_fails():
    rows = [ReplayRecord("STH-1", "AGENT", "a" * 64, "a" * 64, False, "SIMULATED_FAILURE")]
    with pytest.raises(ValueError, match="outside impacted"):
        audit_replay(rows, rp())


def test_impacted_failure_is_isolated():
    rows = [
        ReplayRecord("STH-1", "AGENT", "a" * 64, "a" * 64, True, "SIMULATED_FAILURE"),
        ReplayRecord("STH-2", "AGENT", "b" * 64, "b" * 64, False),
    ]
    audit = audit_replay(rows, rp())
    assert audit.failed_records == 1
    assert audit.isolated_failures == 1
    validate_replay_failure_isolation(rows)


def test_replay_fingerprint_is_deterministic():
    rows = [
        ReplayRecord("STH-2", "PUBLIC", "c" * 64, "c" * 64, False),
        ReplayRecord("STH-1", "AGENT", "a" * 64, "d" * 64, True),
    ]
    assert audit_replay(rows, rp()).replay_fingerprint == audit_replay(reversed(rows), rp()).replay_fingerprint


def test_pointer_update_and_rollback_returns_exact_baseline():
    ids = [f"STH-{i:04d}" for i in range(1, 26)]
    cohort = freeze_publication_cohort(
        cohort_code="COHORT_25",
        candidate_fingerprint="f" * 64,
        eligible_property_ids=ids,
        policy=pp(),
    )
    rows = []
    before = []
    for pid in ids:
        for tier, state, rf in (
            ("AGENT", "a" * 64, "1" * 64),
            ("SELLER", "b" * 64, "2" * 64),
            ("PUBLIC", "c" * 64, "3" * 64),
        ):
            rows.append(PublicationVariant(
                pid, tier, state, "d" * 64, rf,
                "MATERIALIZED_NOT_PUBLISHED", True, False, False
            ))
            before.append(PublicationPointer(pid, tier, "9" * 64, "8" * 64))
    batch = build_publication_batch(cohort=cohort, variants=rows, current_pointers=before)
    assert verify_publication_rollback(before=before, batch=batch) is True
