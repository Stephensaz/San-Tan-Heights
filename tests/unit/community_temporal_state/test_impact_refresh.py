from dataclasses import fields, replace

import pytest

from src.community_temporal_state.snapshot import (
    build_community_state_snapshot,
    certify_snapshot,
    load_snapshot_registry,
    make_manifest_entry,
    make_property_projection,
)
from src.community_temporal_state.delta import (
    build_community_delta,
    certify_delta,
    load_delta_registry,
)
from src.community_temporal_state.impact_refresh import (
    apply_selective_refresh,
    build_selective_refresh_plan,
    load_impact_refresh_registry,
    make_derived_record,
    policy_fingerprint,
    validate_refresh_plan_replay,
    validate_refresh_result_replay,
)

SR = "registries/community_temporal_state/m13-001-community-state-snapshot-v1.0.yaml"
DR = "registries/community_temporal_state/m13-002-community-delta-v1.0.yaml"
IR = "registries/community_temporal_state/m13-003-impact-refresh-v1.0.yaml"
M12_ROOT = "e56a8d039c4e0324ff694d0ea8cd5a190f48be6bb8b761d761a41f8af96e2a35"


def sr():
    return load_snapshot_registry(SR)


def dr():
    return load_delta_registry(DR)


def ir():
    return load_impact_refresh_registry(IR)


def prop(pid="P-1", *, identity="1", phase="2", spatial="3", intelligence="4"):
    return make_property_projection(
        property_id=pid,
        identity_fingerprint=identity * 64,
        phase_fingerprint=phase * 64,
        spatial_fingerprint=spatial * 64,
        intelligence_fingerprint=intelligence * 64,
        freshness_state="CURRENT",
        registry=sr(),
    )


def snap(snapshot_id, observation, cutoff, materialized, props, *, source=()):
    draft = build_community_state_snapshot(
        snapshot_id=snapshot_id,
        community_id="SAN-TAN-HEIGHTS",
        observation_time=observation,
        knowledge_cutoff=cutoff,
        materialized_at=materialized,
        baseline_snapshot_id=None if snapshot_id == "S-1" else "S-1",
        m12_release_certified=True,
        m12_release_certification_root=M12_ROOT,
        source_manifest=source,
        policy_manifest=(),
        runtime_manifest=(),
        property_states=props,
        registry=sr(),
    )
    return certify_snapshot(draft, registry=sr())


def before():
    return snap(
        "S-1",
        "2026-09-18T09:00:00-07:00",
        "2026-09-18T08:50:00-07:00",
        "2026-09-18T09:05:00-07:00",
        (prop("P-1"), prop("P-2")),
    )


def after_identity_change():
    return snap(
        "S-2",
        "2026-09-18T10:00:00-07:00",
        "2026-09-18T09:50:00-07:00",
        "2026-09-18T10:05:00-07:00",
        (prop("P-1", identity="5"), prop("P-2")),
    )


def certified_delta(a=None, b=None):
    a = a or before()
    b = b or after_identity_change()
    d = build_community_delta(
        delta_id="D-1",
        before=a,
        after=b,
        detected_at="2026-09-18T10:06:00-07:00",
        snapshot_registry=sr(),
        delta_registry=dr(),
    )
    return certify_delta(d)


def record(aid, atype, scope_id, snapshot_hash, *, scope="PROPERTY", payload="a", lineage=()):
    return make_derived_record(
        artifact_id=aid,
        artifact_type=atype,
        scope=scope,
        scope_id=scope_id,
        source_snapshot_semantic_hash=snapshot_hash,
        payload_fingerprint=payload * 64,
        lineage_fingerprints=lineage,
    )


def current_records():
    s = before()
    return (
        record("A-1", "COMPARABLE_STRENGTH", "P-1", s.semantic_hash, payload="a"),
        record("A-2", "BUYER_DEPTH", "P-2", s.semantic_hash, payload="b"),
        record("A-3", "SELLER_INTELLIGENCE", "P-1", s.semantic_hash, payload="c"),
        record("A-4", "RESALE_COMPETITION", "SAN-TAN-HEIGHTS", s.semantic_hash, scope="COMMUNITY", payload="d"),
    )


def plan(delta=None, records=None):
    return build_selective_refresh_plan(
        plan_id="PLAN-1",
        delta=delta or certified_delta(),
        current_records=records or current_records(),
        registry=ir(),
    )


def replacement(old, p, *, payload_char="e", snapshot_hash=None, extra_lineage=()):
    decision = next(x for x in p.decisions if x.artifact_id == old.artifact_id)
    return make_derived_record(
        artifact_id=old.artifact_id,
        artifact_type=old.artifact_type,
        scope=old.scope,
        scope_id=old.scope_id,
        source_snapshot_semantic_hash=snapshot_hash or p.after_snapshot_semantic_hash,
        payload_fingerprint=payload_char * 64,
        lineage_fingerprints=(p.delta_fingerprint, decision.decision_fingerprint, *extra_lineage),
    )


def test_property_change_refreshes_only_matching_property_dependencies():
    p = plan()
    assert p.refresh_artifact_ids == ("A-1", "A-3")
    assert p.preserved_artifact_ids == ("A-2", "A-4")
    p1 = next(x for x in p.decisions if x.artifact_id == "A-1")
    p2 = next(x for x in p.decisions if x.artifact_id == "A-2")
    assert p1.decision == "REFRESH_REQUIRED"
    assert "IDENTITY:MODIFIED" in p1.reason_codes
    assert p1.source_change_fingerprints
    assert p2.decision == "NO_IMPACT"
    assert p2.reason_codes == ("NO_GOVERNED_DEPENDENCY_MATCH",)
    assert p2.source_change_fingerprints == ()


def test_plan_is_deterministic_and_policy_fingerprint_is_bound():
    p1 = plan()
    p2 = plan()
    assert p1.plan_fingerprint == p2.plan_fingerprint
    assert p1.dependency_policy_fingerprint == policy_fingerprint(ir())
    assert validate_refresh_plan_replay(p1)


def test_uncertified_delta_fails_closed():
    a = before()
    b = after_identity_change()
    draft = build_community_delta(
        delta_id="D-DRAFT",
        before=a,
        after=b,
        detected_at="2026-09-18T10:06:00-07:00",
        snapshot_registry=sr(),
        delta_registry=dr(),
    )
    with pytest.raises(ValueError, match="CERTIFIED"):
        plan(delta=draft)


def test_tampered_delta_fails_closed():
    d = certified_delta()
    bad = replace(d, highest_materiality="LOW")
    with pytest.raises(ValueError, match="reproducible"):
        plan(delta=bad)


def test_selective_refresh_preserves_unaffected_records_exactly():
    records = current_records()
    p = plan(records=records)
    replacements = tuple(
        replacement(r, p, payload_char="e" if r.artifact_id == "A-1" else "f")
        for r in records
        if r.artifact_id in p.refresh_artifact_ids
    )
    result = apply_selective_refresh(
        result_id="RESULT-1",
        plan=p,
        current_records=records,
        authoritative_replacements=replacements,
        registry=ir(),
    )
    by_id = {x.artifact_id: x for x in result.records}
    old = {x.artifact_id: x for x in records}
    assert by_id["A-2"] is old["A-2"]
    assert by_id["A-4"] is old["A-4"]
    assert by_id["A-1"].record_fingerprint != old["A-1"].record_fingerprint
    assert result.refreshed_artifact_ids == ("A-1", "A-3")
    assert result.preserved_artifact_ids == ("A-2", "A-4")
    assert validate_refresh_result_replay(result)


def test_missing_or_extra_replacement_fails_closed():
    records = current_records()
    p = plan(records=records)
    a1 = replacement(records[0], p)
    with pytest.raises(ValueError, match="exactly match refresh set"):
        apply_selective_refresh(
            result_id="R",
            plan=p,
            current_records=records,
            authoritative_replacements=(a1,),
            registry=ir(),
        )
    extra = record(
        "A-X", "SELLER_INTELLIGENCE", "P-1", p.after_snapshot_semantic_hash,
        payload="9", lineage=(p.delta_fingerprint,),
    )
    a3 = replacement(records[2], p, payload_char="f")
    with pytest.raises(ValueError, match="exactly match refresh set"):
        apply_selective_refresh(
            result_id="R",
            plan=p,
            current_records=records,
            authoritative_replacements=(a1, a3, extra),
            registry=ir(),
        )


def test_wrong_after_snapshot_binding_fails_closed():
    records = current_records()
    p = plan(records=records)
    reps = []
    for r in records:
        if r.artifact_id in p.refresh_artifact_ids:
            reps.append(replacement(r, p, snapshot_hash="0" * 64))
    with pytest.raises(ValueError, match="after-snapshot"):
        apply_selective_refresh(
            result_id="R",
            plan=p,
            current_records=records,
            authoritative_replacements=tuple(reps),
            registry=ir(),
        )


def test_missing_refresh_lineage_fails_closed():
    records = current_records()
    p = plan(records=records)
    reps = []
    for r in records:
        if r.artifact_id in p.refresh_artifact_ids:
            reps.append(
                make_derived_record(
                    artifact_id=r.artifact_id,
                    artifact_type=r.artifact_type,
                    scope=r.scope,
                    scope_id=r.scope_id,
                    source_snapshot_semantic_hash=p.after_snapshot_semantic_hash,
                    payload_fingerprint="e" * 64,
                    lineage_fingerprints=(),
                )
            )
    with pytest.raises(ValueError, match="missing M13-003 refresh lineage"):
        apply_selective_refresh(
            result_id="R",
            plan=p,
            current_records=records,
            authoritative_replacements=tuple(reps),
            registry=ir(),
        )


def test_current_state_drift_after_planning_fails_closed():
    records = current_records()
    p = plan(records=records)
    changed_old = replace(records[0], record_fingerprint="0" * 64)
    drifted = (changed_old, *records[1:])
    reps = tuple(
        replacement(r, p)
        for r in records
        if r.artifact_id in p.refresh_artifact_ids
    )
    with pytest.raises(ValueError, match="drifted"):
        apply_selective_refresh(
            result_id="R",
            plan=p,
            current_records=drifted,
            authoritative_replacements=reps,
            registry=ir(),
        )


def test_manifest_source_change_can_refresh_governed_community_and_property_dependencies():
    a = before()
    src = make_manifest_entry(
        entry_type="MLS",
        entry_id="CURRENT",
        effective_at="2026-09-18T09:15:00-07:00",
        known_at="2026-09-18T09:30:00-07:00",
        fingerprint="9" * 64,
    )
    b = snap(
        "S-2",
        "2026-09-18T10:00:00-07:00",
        "2026-09-18T09:50:00-07:00",
        "2026-09-18T10:05:00-07:00",
        (prop("P-1"), prop("P-2")),
        source=(src,),
    )
    p = plan(delta=certified_delta(a, b))
    assert set(p.refresh_artifact_ids) == {"A-1", "A-2", "A-3", "A-4"}


def test_duplicate_artifact_ids_are_rejected():
    records = current_records()
    with pytest.raises(ValueError, match="duplicate artifact ids"):
        plan(records=(records[0], records[0]))


def test_refresh_result_detects_tampering():
    records = current_records()
    p = plan(records=records)
    reps = tuple(
        replacement(r, p, payload_char="e" if r.artifact_id == "A-1" else "f")
        for r in records
        if r.artifact_id in p.refresh_artifact_ids
    )
    result = apply_selective_refresh(
        result_id="RESULT-1",
        plan=p,
        current_records=records,
        authoritative_replacements=reps,
        registry=ir(),
    )
    assert validate_refresh_result_replay(result)
    assert validate_refresh_result_replay(replace(result, refreshed_artifact_ids=("A-1",))) is False


def test_m13_003_objects_have_no_recommendation_action_publication_or_learning_fields():
    forbidden = {
        "recommendation",
        "seller_message",
        "listing_action",
        "publication_action",
        "price_recommendation",
        "outcome_prediction",
        "learning_score",
        "calibration",
    }
    for cls in (type(plan()), type(plan().decisions[0])):
        assert set(x.name for x in fields(cls)).isdisjoint(forbidden)
