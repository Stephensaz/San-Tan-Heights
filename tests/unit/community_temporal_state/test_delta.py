from dataclasses import replace

import pytest

from src.community_temporal_state.delta import (
    ChangeCause,
    build_community_delta,
    certify_delta,
    load_delta_registry,
    validate_delta_replay,
)
from src.community_temporal_state.snapshot import (
    build_community_state_snapshot,
    certify_snapshot,
    load_snapshot_registry,
    make_manifest_entry,
    make_property_projection,
)

SR = "registries/community_temporal_state/m13-001-community-state-snapshot-v1.0.yaml"
DR = "registries/community_temporal_state/m13-002-community-delta-v1.0.yaml"
M12_ROOT = "e56a8d039c4e0324ff694d0ea8cd5a190f48be6bb8b761d761a41f8af96e2a35"


def sr():
    return load_snapshot_registry(SR)


def dr():
    return load_delta_registry(DR)


def manifest(kind, entry_id, fp, *, effective, known):
    return make_manifest_entry(
        entry_type=kind,
        entry_id=entry_id,
        effective_at=effective,
        known_at=known,
        fingerprint=fp,
    )


def prop(
    pid="P-1",
    *,
    identity="1",
    phase="2",
    spatial="3",
    intelligence="4",
    freshness="CURRENT",
    exclusions=(),
    conflicts=(),
):
    return make_property_projection(
        property_id=pid,
        identity_fingerprint=identity * 64,
        phase_fingerprint=phase * 64,
        spatial_fingerprint=spatial * 64,
        intelligence_fingerprint=intelligence * 64,
        freshness_state=freshness,
        exclusion_codes=exclusions,
        conflict_codes=conflicts,
        registry=sr(),
    )


def snap(
    sid,
    observation,
    cutoff,
    materialized,
    *,
    props=None,
    source=None,
    policy=None,
    runtime=None,
    freshness="CURRENT",
    exclusions=(),
    conflicts=(),
    community="SAN-TAN-HEIGHTS",
):
    s = build_community_state_snapshot(
        snapshot_id=sid,
        community_id=community,
        observation_time=observation,
        knowledge_cutoff=cutoff,
        materialized_at=materialized,
        baseline_snapshot_id=None if sid == "S1" else "S1",
        m12_release_certified=True,
        m12_release_certification_root=M12_ROOT,
        source_manifest=tuple(source or ()),
        policy_manifest=tuple(policy or ()),
        runtime_manifest=tuple(runtime or ()),
        property_states=tuple(props or (prop(),)),
        exclusions=exclusions,
        conflicts=conflicts,
        freshness_state=freshness,
        registry=sr(),
    )
    return certify_snapshot(s, registry=sr())


def before():
    return snap(
        "S1",
        "2026-09-18T09:00:00-07:00",
        "2026-09-18T08:45:00-07:00",
        "2026-09-18T09:05:00-07:00",
        source=(
            manifest("MLS", "MLS-1", "a" * 64, effective="2026-09-18T08:00:00-07:00", known="2026-09-18T08:30:00-07:00"),
        ),
        policy=(
            manifest("MATERIALITY", "POL-1", "b" * 64, effective="2026-09-18T08:00:00-07:00", known="2026-09-18T08:30:00-07:00"),
        ),
        runtime=(
            manifest("ENGINE", "ENG-1", "c" * 64, effective="2026-09-18T08:00:00-07:00", known="2026-09-18T08:30:00-07:00"),
        ),
    )


def after(**overrides):
    kw = dict(
        sid="S2",
        observation="2026-09-18T10:00:00-07:00",
        cutoff="2026-09-18T09:45:00-07:00",
        materialized="2026-09-18T10:05:00-07:00",
        source=(
            manifest("MLS", "MLS-1", "a" * 64, effective="2026-09-18T08:00:00-07:00", known="2026-09-18T08:30:00-07:00"),
        ),
        policy=(
            manifest("MATERIALITY", "POL-1", "b" * 64, effective="2026-09-18T08:00:00-07:00", known="2026-09-18T08:30:00-07:00"),
        ),
        runtime=(
            manifest("ENGINE", "ENG-1", "c" * 64, effective="2026-09-18T08:00:00-07:00", known="2026-09-18T08:30:00-07:00"),
        ),
    )
    kw.update(overrides)
    return snap(**kw)


def delta(a=None, b=None, **overrides):
    kw = dict(
        delta_id="D-1",
        before=a or before(),
        after=b or after(),
        detected_at="2026-09-18T10:06:00-07:00",
        snapshot_registry=sr(),
        delta_registry=dr(),
    )
    kw.update(overrides)
    return build_community_delta(**kw)


def changed(d, *, object_id, field_path):
    rows = [x for x in d.changes if x.object_id == object_id and x.field_path == field_path]
    assert len(rows) == 1
    return rows[0]


def test_identical_semantic_inputs_produce_deterministic_delta():
    assert delta().delta_fingerprint == delta().delta_fingerprint


def test_unchanged_fields_are_explicit_not_silently_dropped():
    d = delta()
    c = changed(d, object_id="P-1", field_path="identity_fingerprint")
    assert c.classification == "UNCHANGED"
    assert c.materiality == "INFORMATIONAL"


def test_property_identity_change_records_exact_before_after_and_unknown_cause_by_default():
    b = after(props=(prop(identity="5"),))
    d = delta(b=b)
    c = changed(d, object_id="P-1", field_path="identity_fingerprint")
    assert c.before_value == "1" * 64
    assert c.after_value == "5" * 64
    assert c.classification == "MODIFIED"
    assert c.change_cause == "UNKNOWN"
    assert c.causation_basis == "UNKNOWN_CAUSE"
    assert c.effective_at == "UNKNOWN"
    assert c.potentially_stale is True


def test_explicit_supported_causation_and_effective_time_are_preserved():
    b = after(props=(prop(identity="5"),))
    key = "PROPERTY:P-1:identity_fingerprint"
    d = delta(
        b=b,
        cause_overrides={key: ChangeCause("REAL_WORLD_CHANGE", "DATA_DRIVEN")},
        effective_at_overrides={key: "2026-09-18T09:20:00-07:00"},
    )
    c = changed(d, object_id="P-1", field_path="identity_fingerprint")
    assert c.change_cause == "REAL_WORLD_CHANGE"
    assert c.causation_basis == "DATA_DRIVEN"
    assert c.effective_at == "2026-09-18T09:20:00-07:00"


def test_unsupported_causation_is_rejected():
    b = after(props=(prop(identity="5"),))
    key = "PROPERTY:P-1:identity_fingerprint"
    with pytest.raises(ValueError, match="unsupported change cause"):
        delta(b=b, cause_overrides={key: ChangeCause("SELLER_MOTIVATION", "DATA_DRIVEN")})


def test_unknown_effective_date_remains_unknown_and_is_not_inferred_from_detection():
    b = after(props=(prop(intelligence="5"),))
    c = changed(delta(b=b), object_id="P-1", field_path="intelligence_fingerprint")
    assert c.effective_at == "UNKNOWN"
    assert c.detected_at == "2026-09-18T10:06:00-07:00"


def test_property_added_and_removed_are_factual_object_changes():
    b = after(props=(prop("P-2"),))
    d = delta(b=b)
    p1 = changed(d, object_id="P-1", field_path="property")
    p2 = changed(d, object_id="P-2", field_path="property")
    assert p1.classification == "REMOVED"
    assert p2.classification == "ADDED"


def test_unknown_to_known_and_known_to_unknown_freshness_transitions():
    a = before()
    known = after(props=(prop(freshness="UNKNOWN"),))
    d1 = delta(a=a, b=known)
    assert changed(d1, object_id="P-1", field_path="freshness_state").classification == "BECAME_UNKNOWN"

    a2 = snap(
        "S1",
        "2026-09-18T09:00:00-07:00",
        "2026-09-18T08:45:00-07:00",
        "2026-09-18T09:05:00-07:00",
        props=(prop(freshness="UNKNOWN"),),
    )
    b2 = after(props=(prop(freshness="CURRENT"),), source=(), policy=(), runtime=())
    d2 = delta(a=a2, b=b2)
    assert changed(d2, object_id="P-1", field_path="freshness_state").classification == "BECAME_KNOWN"


def test_conflict_introduced_and_resolved_are_distinct():
    d1 = delta(b=after(props=(prop(conflicts=("IDENTITY_CONFLICT",)),)))
    assert changed(d1, object_id="P-1", field_path="conflict_codes").classification == "CONFLICT_INTRODUCED"

    a2 = snap(
        "S1",
        "2026-09-18T09:00:00-07:00",
        "2026-09-18T08:45:00-07:00",
        "2026-09-18T09:05:00-07:00",
        props=(prop(conflicts=("IDENTITY_CONFLICT",)),),
    )
    b2 = after(source=(), policy=(), runtime=())
    d2 = delta(a=a2, b=b2)
    assert changed(d2, object_id="P-1", field_path="conflict_codes").classification == "CONFLICT_RESOLVED"


def test_suppression_and_reactivation_are_distinct():
    d1 = delta(b=after(props=(prop(exclusions=("NOT_ELIGIBLE",)),)))
    assert changed(d1, object_id="P-1", field_path="exclusion_codes").classification == "SUPPRESSED"

    a2 = snap(
        "S1",
        "2026-09-18T09:00:00-07:00",
        "2026-09-18T08:45:00-07:00",
        "2026-09-18T09:05:00-07:00",
        props=(prop(exclusions=("NOT_ELIGIBLE",)),),
    )
    b2 = after(source=(), policy=(), runtime=())
    d2 = delta(a=a2, b=b2)
    assert changed(d2, object_id="P-1", field_path="exclusion_codes").classification == "REACTIVATED"


def test_late_arriving_source_is_became_known_with_data_driven_cause():
    late = manifest(
        "DEED",
        "D-1",
        "d" * 64,
        effective="2026-09-18T08:20:00-07:00",
        known="2026-09-18T09:20:00-07:00",
    )
    b = after(source=before().source_manifest + (late,))
    d = delta(b=b)
    c = changed(d, object_id="DEED:D-1", field_path="manifest_entry")
    assert c.classification == "BECAME_KNOWN"
    assert c.change_cause == "NEWLY_OBSERVED_FACT"
    assert c.causation_basis == "DATA_DRIVEN"
    assert c.effective_at == "2026-09-18T08:20:00-07:00"


def test_policy_manifest_change_is_rule_driven_not_real_world_change():
    pol = manifest(
        "MATERIALITY",
        "POL-1",
        "d" * 64,
        effective="2026-09-18T09:15:00-07:00",
        known="2026-09-18T09:20:00-07:00",
    )
    d = delta(b=after(policy=(pol,)))
    c = changed(d, object_id="MATERIALITY:POL-1", field_path="manifest_entry")
    assert c.change_cause == "CLASSIFICATION_CHANGE"
    assert c.causation_basis == "RULE_DRIVEN"


def test_runtime_manifest_change_is_engine_driven_not_data_driven():
    eng = manifest(
        "ENGINE",
        "ENG-1",
        "d" * 64,
        effective="2026-09-18T09:15:00-07:00",
        known="2026-09-18T09:20:00-07:00",
    )
    d = delta(b=after(runtime=(eng,)))
    c = changed(d, object_id="ENGINE:ENG-1", field_path="manifest_entry")
    assert c.change_cause == "ENGINE_CHANGE"
    assert c.causation_basis == "ENGINE_DRIVEN"


def test_identity_change_emits_descriptive_potential_staleness_edge_only():
    d = delta(b=after(props=(prop(identity="5"),)))
    c = changed(d, object_id="P-1", field_path="identity_fingerprint")
    edges = [x for x in d.impact_edges if x.source_change_fingerprint == c.change_fingerprint]
    assert len(edges) == 1
    assert edges[0].affected_object_type == "DERIVED_INTELLIGENCE"
    assert edges[0].affected_object_id == "P-1"
    assert edges[0].potentially_stale is True
    assert not hasattr(edges[0], "refresh_job_id")
    assert not hasattr(edges[0], "invalidated")


def test_intelligence_change_does_not_claim_upstream_staleness():
    d = delta(b=after(props=(prop(intelligence="5"),)))
    c = changed(d, object_id="P-1", field_path="intelligence_fingerprint")
    assert c.potentially_stale is False
    assert not [x for x in d.impact_edges if x.source_change_fingerprint == c.change_fingerprint]


def test_conflict_introduction_is_critical_materiality():
    d = delta(b=after(props=(prop(conflicts=("IDENTITY_CONFLICT",)),)))
    c = changed(d, object_id="P-1", field_path="conflict_codes")
    assert c.materiality == "CRITICAL"
    assert d.highest_materiality == "CRITICAL"


def test_only_comparison_eligible_certified_snapshots_are_accepted():
    draft = build_community_state_snapshot(
        snapshot_id="DRAFT",
        community_id="SAN-TAN-HEIGHTS",
        observation_time="2026-09-18T08:00:00-07:00",
        knowledge_cutoff="2026-09-18T07:45:00-07:00",
        materialized_at="2026-09-18T08:05:00-07:00",
        baseline_snapshot_id=None,
        m12_release_certified=True,
        m12_release_certification_root=M12_ROOT,
        source_manifest=(),
        policy_manifest=(),
        runtime_manifest=(),
        property_states=(prop(),),
        registry=sr(),
    )
    with pytest.raises(ValueError, match="CERTIFIED"):
        delta(a=draft)


def test_stale_certified_snapshot_is_rejected_as_not_comparison_eligible():
    stale = snap(
        "S1",
        "2026-09-18T09:00:00-07:00",
        "2026-09-18T08:45:00-07:00",
        "2026-09-18T09:05:00-07:00",
        freshness="STALE",
    )
    with pytest.raises(ValueError, match="not comparison eligible"):
        delta(a=stale)


def test_different_communities_fail_closed():
    other = after(community="OTHER")
    with pytest.raises(ValueError, match="community mismatch"):
        delta(b=other)


def test_reverse_chronology_fails_closed():
    with pytest.raises(ValueError, match="chronologically later"):
        build_community_delta(
            delta_id="D-X",
            before=after(),
            after=before(),
            detected_at="2026-09-18T10:06:00-07:00",
            snapshot_registry=sr(),
            delta_registry=dr(),
        )


def test_detection_time_cannot_precede_after_snapshot():
    with pytest.raises(ValueError, match="cannot precede"):
        delta(detected_at="2026-09-18T09:59:00-07:00")


def test_tampered_snapshot_fails_before_comparison():
    a = before()
    tampered = replace(a, community_id="SAN-TAN-HEIGHTS-TAMPER")
    with pytest.raises(ValueError, match="nonreproducible"):
        delta(a=tampered)


def test_delta_replay_detects_tampering():
    d = delta(b=after(props=(prop(identity="5"),)))
    assert validate_delta_replay(d)
    tampered = replace(d, highest_materiality="LOW")
    assert validate_delta_replay(tampered) is False
    with pytest.raises(ValueError, match="nonreproducible"):
        certify_delta(tampered)


def test_delta_certification_is_explicit_and_immutable():
    d = delta(b=after(props=(prop(identity="5"),)))
    certified = certify_delta(d)
    assert d.certification_state == "DRAFT"
    assert certified.certification_state == "CERTIFIED"
    assert certified.delta_fingerprint == d.delta_fingerprint


def test_lineage_contains_both_snapshot_hashes_and_m12_root():
    d = delta()
    assert before().semantic_hash in d.lineage_fingerprints
    assert after().semantic_hash in d.lineage_fingerprints
    assert M12_ROOT in d.lineage_fingerprints


def test_delta_objects_have_no_recommendation_action_refresh_or_publication_fields():
    d = delta()
    names = set(d.__dataclass_fields__)
    forbidden = {
        "recommendation",
        "listing_action",
        "refresh_jobs",
        "recalculation",
        "publication_action",
        "seller_message",
        "price_recommendation",
    }
    assert names.isdisjoint(forbidden)


def test_m13_002_module_exposes_no_m13_003_refresh_or_propagation_api():
    import src.community_temporal_state.delta as mod
    names = set(dir(mod))
    assert "propagate_impact" not in names
    assert "refresh_affected_intelligence" not in names
    assert "enqueue_refresh" not in names
    assert "invalidate_downstream" not in names
