from dataclasses import replace

import pytest

from src.community_temporal_state.snapshot import (
    build_community_state_snapshot, certify_snapshot, load_snapshot_registry,
    make_property_projection,
)
from src.community_temporal_state.delta import (
    build_community_delta, certify_delta, load_delta_registry,
)
from src.community_temporal_state.impact_refresh import (
    apply_selective_refresh, build_selective_refresh_plan, load_impact_refresh_registry,
    make_derived_record,
)
from src.community_temporal_state.history import (
    append_correction, append_entries, build_temporal_ledger, community_history_summary,
    delta_entries, historical_view, load_temporal_history_registry, refresh_entries,
    snapshot_entries, validate_ledger_replay,
)

SR="registries/community_temporal_state/m13-001-community-state-snapshot-v1.0.yaml"
DR="registries/community_temporal_state/m13-002-community-delta-v1.0.yaml"
IR="registries/community_temporal_state/m13-003-impact-refresh-v1.0.yaml"
HR="registries/community_temporal_state/m13-004-temporal-history-v1.0.yaml"
M12_ROOT="e56a8d039c4e0324ff694d0ea8cd5a190f48be6bb8b761d761a41f8af96e2a35"


def sr(): return load_snapshot_registry(SR)
def dr(): return load_delta_registry(DR)
def ir(): return load_impact_refresh_registry(IR)
def hr(): return load_temporal_history_registry(HR)


def prop(identity="1"):
    return make_property_projection(
        property_id="P-1",
        identity_fingerprint=identity*64,
        phase_fingerprint="2"*64,
        spatial_fingerprint="3"*64,
        intelligence_fingerprint="4"*64,
        freshness_state="CURRENT",
        registry=sr(),
    )


def snap(snapshot_id, observation, cutoff, materialized, identity="1"):
    d=build_community_state_snapshot(
        snapshot_id=snapshot_id,
        community_id="SAN-TAN-HEIGHTS",
        observation_time=observation,
        knowledge_cutoff=cutoff,
        materialized_at=materialized,
        baseline_snapshot_id=None if snapshot_id=="S-1" else "S-1",
        m12_release_certified=True,
        m12_release_certification_root=M12_ROOT,
        source_manifest=(), policy_manifest=(), runtime_manifest=(),
        property_states=(prop(identity),),
        registry=sr(),
    )
    return certify_snapshot(d, registry=sr())


def before():
    return snap("S-1","2026-09-18T09:00:00-07:00","2026-09-18T08:50:00-07:00","2026-09-18T09:05:00-07:00")


def after():
    return snap("S-2","2026-09-18T10:00:00-07:00","2026-09-18T09:50:00-07:00","2026-09-18T10:05:00-07:00","5")


def delta():
    d=build_community_delta(
        delta_id="D-1", before=before(), after=after(),
        detected_at="2026-09-18T10:06:00-07:00",
        snapshot_registry=sr(), delta_registry=dr(),
    )
    return certify_delta(d)


def refresh_state():
    old=make_derived_record(
        artifact_id="A-1", artifact_type="COMPARABLE_STRENGTH",
        scope="PROPERTY", scope_id="P-1",
        source_snapshot_semantic_hash=before().semantic_hash,
        payload_fingerprint="a"*64,
    )
    p=build_selective_refresh_plan(
        plan_id="PLAN-1", delta=delta(), current_records=(old,), registry=ir()
    )
    decision=p.decisions[0]
    new=make_derived_record(
        artifact_id="A-1", artifact_type="COMPARABLE_STRENGTH",
        scope="PROPERTY", scope_id="P-1",
        source_snapshot_semantic_hash=p.after_snapshot_semantic_hash,
        payload_fingerprint="b"*64,
        lineage_fingerprints=(p.delta_fingerprint, decision.decision_fingerprint),
    )
    result=apply_selective_refresh(
        result_id="RESULT-1", plan=p, current_records=(old,),
        authoritative_replacements=(new,), registry=ir()
    )
    return p,result


def ledger():
    entries=(
        *snapshot_entries(before(), recorded_at="2026-09-18T09:06:00-07:00", registry=hr()),
        *delta_entries(delta(), recorded_at="2026-09-18T10:07:00-07:00", registry=hr()),
    )
    return build_temporal_ledger(
        ledger_id="LEDGER-1", community_id="SAN-TAN-HEIGHTS", entries=entries
    )


def test_snapshot_and_delta_history_is_append_only_and_reproducible():
    l=ledger()
    assert validate_ledger_replay(l)
    assert any(x.entry_type=="SNAPSHOT" for x in l.entries)
    assert any(x.entry_type=="DELTA" for x in l.entries)


def test_reality_time_and_knowledge_time_are_distinct():
    e=next(x for x in ledger().entries if x.entry_type=="DELTA")
    assert e.valid_from != e.known_at
    assert e.known_at=="2026-09-18T10:06:00-07:00"


def test_unknown_effective_time_is_not_fabricated():
    e=next(x for x in ledger().entries if x.entry_type=="DELTA")
    assert "EFFECTIVE_TIME_UNKNOWN_USED_FIRST_OBSERVED" in e.limitations
    assert e.valid_from=="2026-09-18T10:00:00-07:00"


def test_correction_appends_without_rewriting_target():
    l=ledger()
    target=next(x for x in l.entries if x.scope=="PROPERTY" and x.entry_type=="SNAPSHOT")
    updated=append_correction(
        l, correction_id="CORR-1",
        target_entry_fingerprint=target.entry_fingerprint,
        corrected_value={"corrected":True},
        valid_from="2026-09-18T09:00:00-07:00",
        known_at="2026-09-18T11:00:00-07:00",
        recorded_at="2026-09-18T11:01:00-07:00",
        registry=hr(), evidence_fingerprints=("9"*64,),
    )
    assert len(updated.entries)==len(l.entries)+1
    assert target in updated.entries
    corr=next(x for x in updated.entries if x.entry_type=="CORRECTION")
    assert corr.previous_entry_fingerprint==target.entry_fingerprint


def test_append_rejects_reuse_of_entry_identity():
    l=ledger()
    with pytest.raises(ValueError,match="duplicate entry ids"):
        append_entries(l,new_entries=(l.entries[0],))


def test_true_then_and_known_then_are_deterministic():
    l=ledger()
    a=historical_view(
        l, mode="TRUE_THEN", scope="PROPERTY", scope_id="P-1",
        as_of_valid_time="2026-09-18T09:30:00-07:00", registry=hr()
    )
    b=historical_view(
        l, mode="TRUE_THEN", scope="PROPERTY", scope_id="P-1",
        as_of_valid_time="2026-09-18T09:30:00-07:00", registry=hr()
    )
    assert a.view_fingerprint==b.view_fingerprint
    k=historical_view(
        l, mode="KNOWN_THEN", scope="PROPERTY", scope_id="P-1",
        as_of_valid_time="2026-09-18T10:30:00-07:00",
        as_of_knowledge_time="2026-09-18T09:30:00-07:00", registry=hr()
    )
    assert all(x.known_at <= "2026-09-18T09:30:00-07:00" for x in k.entries)


def test_known_then_requires_knowledge_cutoff():
    with pytest.raises(ValueError,match="requires as_of_knowledge_time"):
        historical_view(
            ledger(), mode="KNOWN_THEN", scope="PROPERTY", scope_id="P-1",
            as_of_valid_time="2026-09-18T10:00:00-07:00", registry=hr()
        )


def test_refresh_lineage_is_materialized():
    p,r=refresh_state()
    rows=refresh_entries(
        community_id="SAN-TAN-HEIGHTS", plan=p, result=r,
        known_at="2026-09-18T10:10:00-07:00",
        recorded_at="2026-09-18T10:11:00-07:00", registry=hr()
    )
    assert len(rows)==1
    e=rows[0]
    assert e.originating_delta_fingerprint==p.delta_fingerprint
    assert e.refresh_plan_fingerprint==p.plan_fingerprint
    assert e.refresh_result_fingerprint==r.result_fingerprint


def test_refresh_lineage_rejects_tampered_result():
    p,r=refresh_state()
    bad=replace(r, result_fingerprint="0"*64)
    with pytest.raises(ValueError,match="reproducible"):
        refresh_entries(
            community_id="SAN-TAN-HEIGHTS", plan=p, result=bad,
            known_at="2026-09-18T10:10:00-07:00",
            recorded_at="2026-09-18T10:11:00-07:00", registry=hr()
        )


def test_ledger_tamper_detection():
    l=ledger()
    assert validate_ledger_replay(l)
    assert validate_ledger_replay(replace(l, community_id="OTHER")) is False


def test_community_summary_is_read_only_deterministic():
    l=ledger()
    a=community_history_summary(l)
    b=community_history_summary(l)
    assert a==b
    assert a["entry_count"]==len(l.entries)


def test_history_objects_expose_no_mutating_or_recommendation_surface():
    l=ledger()
    forbidden={"recommendation","listing_action","publish","execute","delete_history","rewrite_history"}
    assert set(l.__dataclass_fields__).isdisjoint(forbidden)
