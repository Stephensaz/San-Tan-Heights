from dataclasses import replace

import pytest

from src.community_temporal_state.snapshot import (
    build_community_state_snapshot,
    certify_snapshot,
    load_snapshot_registry,
    make_manifest_entry,
    make_property_projection,
    validate_comparison_eligibility,
    validate_snapshot_replay,
)

R = "registries/community_temporal_state/m13-001-community-state-snapshot-v1.0.yaml"
M12_ROOT = "e56a8d039c4e0324ff694d0ea8cd5a190f48be6bb8b761d761a41f8af96e2a35"


def reg():
    return load_snapshot_registry(R)


def manifest(entry_type, entry_id, fp, *, effective="2026-09-18T08:00:00-07:00", known="2026-09-18T08:30:00-07:00"):
    return make_manifest_entry(
        entry_type=entry_type,
        entry_id=entry_id,
        effective_at=effective,
        known_at=known,
        fingerprint=fp,
    )


def prop(pid="P-1", freshness="CURRENT", conflicts=()):
    return make_property_projection(
        property_id=pid,
        identity_fingerprint="1" * 64,
        phase_fingerprint="2" * 64,
        spatial_fingerprint="3" * 64,
        intelligence_fingerprint="4" * 64,
        freshness_state=freshness,
        exclusion_codes=(),
        conflict_codes=conflicts,
        registry=reg(),
    )


def snapshot(**overrides):
    kw = dict(
        snapshot_id="SNAP-1",
        community_id="SAN-TAN-HEIGHTS",
        observation_time="2026-09-18T09:00:00-07:00",
        knowledge_cutoff="2026-09-18T08:45:00-07:00",
        materialized_at="2026-09-18T09:05:00-07:00",
        baseline_snapshot_id=None,
        m12_release_certified=True,
        m12_release_certification_root=M12_ROOT,
        source_manifest=(manifest("SOURCE", "S1", "a" * 64),),
        policy_manifest=(manifest("POLICY", "P1", "b" * 64),),
        runtime_manifest=(manifest("RUNTIME", "R1", "c" * 64),),
        property_states=(prop(),),
        exclusions=(),
        conflicts=(),
        freshness_state="CURRENT",
        registry=reg(),
    )
    kw.update(overrides)
    return build_community_state_snapshot(**kw)


def test_snapshot_is_deterministic_for_identical_semantic_state():
    assert snapshot().semantic_hash == snapshot().semantic_hash


def test_materialization_time_does_not_change_semantic_hash():
    a = snapshot(materialized_at="2026-09-18T09:05:00-07:00")
    b = snapshot(snapshot_id="SNAP-2", materialized_at="2026-09-18T09:15:00-07:00")
    assert a.semantic_hash == b.semantic_hash
    assert a.record_hash != b.record_hash


def test_property_order_does_not_change_semantic_hash():
    p1 = prop("P-1")
    p2 = prop("P-2")
    a = snapshot(property_states=(p1, p2))
    b = snapshot(snapshot_id="SNAP-2", property_states=(p2, p1))
    assert a.semantic_hash == b.semantic_hash
    assert a.corpus_property_ids == ("P-1", "P-2")


def test_manifest_order_does_not_change_semantic_hash():
    s1 = manifest("SOURCE", "S1", "a" * 64)
    s2 = manifest("SOURCE", "S2", "d" * 64)
    a = snapshot(source_manifest=(s1, s2))
    b = snapshot(snapshot_id="SNAP-2", source_manifest=(s2, s1))
    assert a.semantic_hash == b.semantic_hash


def test_snapshot_preserves_exact_m12_release_root():
    assert snapshot().m12_release_certification_root == M12_ROOT


def test_uncertified_m12_fails_closed():
    with pytest.raises(ValueError, match="released certified M12 baseline required"):
        snapshot(m12_release_certified=False)


def test_wrong_m12_root_fails_closed():
    with pytest.raises(ValueError, match="root mismatch"):
        snapshot(m12_release_certification_root="0" * 64)


def test_knowledge_cutoff_cannot_exceed_observation_time():
    with pytest.raises(ValueError, match="knowledge_cutoff cannot be after"):
        snapshot(knowledge_cutoff="2026-09-18T09:01:00-07:00")


def test_future_known_source_fails_closed():
    future = manifest("SOURCE", "FUTURE", "d" * 64, known="2026-09-18T08:50:00-07:00")
    with pytest.raises(ValueError, match="knowledge cutoff violation"):
        snapshot(source_manifest=(future,))


def test_future_effective_source_fails_closed():
    future = manifest(
        "SOURCE",
        "FUTURE",
        "d" * 64,
        effective="2026-09-18T09:01:00-07:00",
        known="2026-09-18T08:40:00-07:00",
    )
    with pytest.raises(ValueError, match="future-effective"):
        snapshot(source_manifest=(future,))


def test_manifest_entry_identity_must_be_unique():
    duplicate_a = manifest("SOURCE", "S1", "a" * 64)
    duplicate_b = manifest("SOURCE", "S1", "d" * 64)
    with pytest.raises(ValueError, match="identity must be unique"):
        snapshot(source_manifest=(duplicate_a, duplicate_b))


def test_property_id_must_resolve_once():
    with pytest.raises(ValueError, match="resolve exactly once"):
        snapshot(property_states=(prop("P-1"), prop("P-1")))


@pytest.mark.parametrize(
    "flag,code",
    [
        ("source_drift", "SOURCE_DRIFT"),
        ("policy_drift", "POLICY_DRIFT"),
        ("runtime_drift", "RUNTIME_DRIFT"),
    ],
)
def test_manifest_drift_is_explicit_and_blocks_certification(flag, code):
    s = snapshot(**{flag: True})
    assert code in s.blocking_conditions
    assert s.reproducible is False
    with pytest.raises(ValueError, match="blocking conditions"):
        certify_snapshot(s, registry=reg())


def test_unresolved_snapshot_conflict_blocks_certification():
    s = snapshot(conflicts=("IDENTITY_CONFLICT",))
    assert "UNRESOLVED_CONFLICT" in s.blocking_conditions
    with pytest.raises(ValueError, match="blocking conditions"):
        certify_snapshot(s, registry=reg())


def test_certified_current_snapshot_is_comparison_eligible():
    certified = certify_snapshot(snapshot(), registry=reg())
    assert certified.certification_state == "CERTIFIED"
    assert certified.comparison_eligible is True
    validate_comparison_eligibility(certified, registry=reg())


def test_stale_certified_snapshot_is_not_comparison_eligible():
    certified = certify_snapshot(snapshot(freshness_state="STALE"), registry=reg())
    assert certified.certification_state == "CERTIFIED"
    assert certified.comparison_eligible is False
    with pytest.raises(ValueError, match="not comparison eligible"):
        validate_comparison_eligibility(certified, registry=reg())


def test_draft_snapshot_cannot_feed_comparison():
    with pytest.raises(ValueError, match="requires CERTIFIED"):
        validate_comparison_eligibility(snapshot(), registry=reg())


def test_replay_detects_semantic_tampering():
    original = snapshot()
    tampered = replace(original, community_id="OTHER")
    assert validate_snapshot_replay(tampered) is False
    with pytest.raises(ValueError, match="nonreproducible"):
        certify_snapshot(tampered, registry=reg())


def test_projection_contains_only_governed_fingerprints_and_states():
    p = prop()
    assert not hasattr(p, "owner_name")
    assert not hasattr(p, "seller_motivation")
    assert not hasattr(p, "list_price")
    assert not hasattr(p, "recommendation")


def test_module_exposes_no_change_detection_or_impact_propagation_engine():
    import src.community_temporal_state.snapshot as mod
    names = set(dir(mod))
    assert "detect_changes" not in names
    assert "compute_delta" not in names
    assert "propagate_impact" not in names
