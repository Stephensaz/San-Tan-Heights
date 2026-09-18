from copy import deepcopy
from dataclasses import replace

import pytest

from src.community_temporal_state.delta import (
    build_community_delta,
    certify_delta,
    load_delta_registry,
)
from src.community_temporal_state.impact_refresh import (
    build_refresh_plan,
    certify_refresh_plan,
    load_refresh_registry,
    make_certified_intelligence_artifact,
    promote_staged_refresh,
    stage_selective_refresh,
    validate_refresh_plan_replay,
)
from src.community_temporal_state.snapshot import (
    build_community_state_snapshot,
    certify_snapshot,
    load_snapshot_registry,
    make_property_projection,
)

SR="registries/community_temporal_state/m13-001-community-state-snapshot-v1.0.yaml"
DR="registries/community_temporal_state/m13-002-community-delta-v1.0.yaml"
RR="registries/community_temporal_state/m13-003-selective-refresh-v1.0.yaml"
M12_ROOT="e56a8d039c4e0324ff694d0ea8cd5a190f48be6bb8b761d761a41f8af96e2a35"


def sr(): return load_snapshot_registry(SR)
def dr(): return load_delta_registry(DR)
def rr(): return load_refresh_registry(RR)


def prop(pid="P-1", *, identity="1", intelligence="4", exclusions=(), conflicts=()):
    return make_property_projection(
        property_id=pid,
        identity_fingerprint=identity*64,
        phase_fingerprint="2"*64,
        spatial_fingerprint="3"*64,
        intelligence_fingerprint=intelligence*64,
        freshness_state="CURRENT",
        exclusion_codes=exclusions,
        conflict_codes=conflicts,
        registry=sr(),
    )


def snap(sid, observation, cutoff, materialized, props):
    value=build_community_state_snapshot(
        snapshot_id=sid,
        community_id="SAN-TAN-HEIGHTS",
        observation_time=observation,
        knowledge_cutoff=cutoff,
        materialized_at=materialized,
        baseline_snapshot_id=None if sid=="S1" else "S1",
        m12_release_certified=True,
        m12_release_certification_root=M12_ROOT,
        source_manifest=(),
        policy_manifest=(),
        runtime_manifest=(),
        property_states=props,
        registry=sr(),
    )
    return certify_snapshot(value,registry=sr())


def delta(*, before_props, after_props, delta_id="D-1"):
    a=snap("S1","2026-09-18T09:00:00-07:00","2026-09-18T08:45:00-07:00","2026-09-18T09:05:00-07:00",before_props)
    b=snap("S2","2026-09-18T10:00:00-07:00","2026-09-18T09:45:00-07:00","2026-09-18T10:05:00-07:00",after_props)
    d=build_community_delta(
        delta_id=delta_id,before=a,after=b,detected_at="2026-09-18T10:06:00-07:00",
        snapshot_registry=sr(),delta_registry=dr(),
    )
    return certify_delta(d)


def artifact(
    aid,
    pid,
    *,
    kind="BUYER_DEPTH",
    domains=("IDENTITY",),
    value="a",
    suppressed=False,
    version=1,
):
    return make_certified_intelligence_artifact(
        artifact_id=aid,
        property_id=pid,
        intelligence_type=kind,
        dependency_domains=domains,
        value_fingerprint=value*64,
        lineage_fingerprints=("9"*64,),
        engine_version="ENGINE-v1",
        ruleset_version="RULES-v1",
        artifact_version=version,
        suppressed=suppressed,
    )


def plan(d, artifacts, registry=None):
    return certify_refresh_plan(build_refresh_plan(
        plan_id="PLAN-1",delta=d,current_artifacts=artifacts,registry=registry or rr()
    ))


def deterministic_refresher(artifact, changes, frozen_input, engine, ruleset):
    seed="|".join([
        artifact.artifact_fingerprint,
        frozen_input,
        engine,
        ruleset,
        *sorted(x.change_fingerprint for x in changes),
    ])
    import hashlib
    return hashlib.sha256(seed.encode()).hexdigest()


def stage(p, d, artifacts, **overrides):
    refreshers={x.intelligence_type:deterministic_refresher for x in artifacts}
    engines={x.intelligence_type:"ENGINE-v2" for x in artifacts}
    rulesets={x.intelligence_type:"RULES-v2" for x in artifacts}
    frozen={x.artifact_id:("f"*64) for x in artifacts}
    kw=dict(
        execution_id="EXEC-1",plan=p,delta=d,current_artifacts=artifacts,
        refreshers=refreshers,engine_versions=engines,ruleset_versions=rulesets,
        frozen_input_fingerprints=frozen,
    )
    kw.update(overrides)
    return stage_selective_refresh(**kw)


def decision(p, aid):
    rows=[x for x in p.decisions if x.artifact_id==aid]
    assert len(rows)==1
    return rows[0]


def test_certified_delta_required():
    d=delta(before_props=(prop(),),after_props=(prop(identity="5"),))
    draft=replace(d,certification_state="DRAFT")
    with pytest.raises(ValueError,match="certified M13-002 delta required"):
        build_refresh_plan(plan_id="P",delta=draft,current_artifacts=(artifact("A","P-1"),),registry=rr())


def test_property_change_refreshes_only_same_property_with_matching_dependency():
    d=delta(
        before_props=(prop("P-1"),prop("P-2")),
        after_props=(prop("P-1",identity="5"),prop("P-2")),
    )
    a1=artifact("A1","P-1")
    a2=artifact("A2","P-2")
    p=plan(d,(a2,a1))
    assert decision(p,"A1").disposition=="REFRESH_REQUIRED"
    assert decision(p,"A2").disposition=="NO_IMPACT"
    assert p.targeted_artifact_ids==("A1",)
    assert p.no_impact_artifact_ids==("A2",)


def test_dependency_domain_mismatch_is_proven_no_impact():
    d=delta(before_props=(prop(),),after_props=(prop(identity="5"),))
    a=artifact("A","P-1",domains=("INTELLIGENCE",))
    p=plan(d,(a,))
    dec=decision(p,"A")
    assert dec.disposition=="NO_IMPACT"
    assert dec.reason_codes==("NO_MATCHING_DEPENDENCY_CHANGE",)


def test_intelligence_change_is_revalidate_only_without_mutation():
    d=delta(before_props=(prop(),),after_props=(prop(intelligence="5"),))
    a=artifact("A","P-1",domains=("INTELLIGENCE",))
    p=plan(d,(a,))
    assert decision(p,"A").disposition=="REVALIDATE_ONLY"
    e=stage(p,d,(a,))
    assert e.status=="STAGED"
    assert e.staged_artifacts==()
    assert e.active_artifacts==(a,)
    assert e.proofs[0].action_taken=="REVALIDATE_ONLY_NO_MUTATION"


def test_suppression_is_staged_not_immediately_mutated():
    d=delta(before_props=(prop(),),after_props=(prop(exclusions=("SUPPRESS",)),))
    a=artifact("A","P-1",domains=("GOVERNANCE",),suppressed=False)
    p=plan(d,(a,))
    assert decision(p,"A").disposition=="SUPPRESS"
    e=stage(p,d,(a,))
    assert e.status=="STAGED"
    assert e.active_artifacts==(a,)
    assert e.staged_artifacts[0].suppressed is True
    assert a.suppressed is False


def test_unsuppression_is_staged():
    d=delta(
        before_props=(prop(exclusions=("SUPPRESS",)),),
        after_props=(prop(),),
    )
    a=artifact("A","P-1",domains=("GOVERNANCE",),suppressed=True)
    p=plan(d,(a,))
    assert decision(p,"A").disposition=="UNSUPPRESS"
    e=stage(p,d,(a,))
    assert e.staged_artifacts[0].suppressed is False


def test_conflict_introduction_blocks_execution_and_preserves_prior_state():
    d=delta(before_props=(prop(),),after_props=(prop(conflicts=("IDENTITY_CONFLICT",)),))
    a=artifact("A","P-1",domains=("GOVERNANCE",))
    p=plan(d,(a,))
    assert decision(p,"A").disposition=="BLOCKED"
    e=stage(p,d,(a,))
    assert e.status=="BLOCKED"
    assert e.active_artifacts==(a,)
    assert e.staged_artifacts==()


def test_unknown_impact_blocks_instead_of_guessing():
    d=delta(before_props=(prop(),),after_props=(prop(identity="5"),))
    a=artifact("A","P-1",domains=("IDENTITY",))
    registry=deepcopy(rr())
    del registry["dependency_rules"]["IDENTITY"]
    p=plan(d,(a,),registry=registry)
    assert decision(p,"A").disposition=="UNKNOWN_IMPACT"
    assert p.blocked_artifact_ids==("A",)


def test_refresh_plan_is_deterministic_and_input_order_independent():
    d=delta(
        before_props=(prop("P-1"),prop("P-2")),
        after_props=(prop("P-1",identity="5"),prop("P-2")),
    )
    a1,a2=artifact("A1","P-1"),artifact("A2","P-2")
    p1=plan(d,(a1,a2))
    p2=plan(d,(a2,a1))
    assert p1.plan_fingerprint==p2.plan_fingerprint


def test_refresh_plan_tamper_is_detected():
    d=delta(before_props=(prop(),),after_props=(prop(identity="5"),))
    p=plan(d,(artifact("A","P-1"),))
    assert validate_refresh_plan_replay(p)
    bad=replace(p,targeted_artifact_ids=())
    assert validate_refresh_plan_replay(bad) is False


def test_stage_requires_certified_plan():
    d=delta(before_props=(prop(),),after_props=(prop(identity="5"),))
    a=artifact("A","P-1")
    p=build_refresh_plan(plan_id="PLAN-1",delta=d,current_artifacts=(a,),registry=rr())
    with pytest.raises(ValueError,match="certified refresh plan required"):
        stage(p,d,(a,))


def test_stage_requires_exact_current_artifact_set():
    d=delta(before_props=(prop(),),after_props=(prop(identity="5"),))
    a=artifact("A","P-1")
    p=plan(d,(a,))
    with pytest.raises(ValueError,match="does not match certified plan"):
        stage_selective_refresh(
            execution_id="E",plan=p,delta=d,current_artifacts=(),
            refreshers={},engine_versions={},ruleset_versions={},frozen_input_fingerprints={},
        )


def test_refresh_requires_frozen_input_fingerprint_and_preserves_prior_on_failure():
    d=delta(before_props=(prop(),),after_props=(prop(identity="5"),))
    a=artifact("A","P-1")
    p=plan(d,(a,))
    e=stage(p,d,(a,),frozen_input_fingerprints={})
    assert e.status=="FAILED"
    assert e.active_artifacts==(a,)
    assert e.staged_artifacts==()
    assert any("missing frozen input fingerprint" in x for x in e.blocking_reasons)


def test_refresh_requires_exact_engine_and_ruleset_versions():
    d=delta(before_props=(prop(),),after_props=(prop(identity="5"),))
    a=artifact("A","P-1")
    p=plan(d,(a,))
    e=stage(p,d,(a,),engine_versions={},ruleset_versions={})
    assert e.status=="FAILED"
    assert e.active_artifacts==(a,)
    assert any("engine and ruleset" in x for x in e.blocking_reasons)


def test_missing_refresher_fails_without_partial_promotion():
    d=delta(before_props=(prop(),),after_props=(prop(identity="5"),))
    a=artifact("A","P-1")
    p=plan(d,(a,))
    e=stage(p,d,(a,),refreshers={})
    assert e.status=="FAILED"
    assert e.active_artifacts==(a,)
    assert e.staged_artifacts==()


def test_nondeterministic_refresher_is_rejected_and_prior_remains_active():
    d=delta(before_props=(prop(),),after_props=(prop(identity="5"),))
    a=artifact("A","P-1")
    p=plan(d,(a,))
    state={"n":0}
    def nondeterministic(*args):
        state["n"]+=1
        return ("a" if state["n"]==1 else "b")*64
    e=stage(p,d,(a,),refreshers={"BUYER_DEPTH":nondeterministic})
    assert e.status=="FAILED"
    assert e.active_artifacts==(a,)
    assert any("nondeterministic" in x for x in e.blocking_reasons)


def test_all_targeted_refreshes_stage_before_any_promotion():
    d=delta(
        before_props=(prop("P-1"),prop("P-2")),
        after_props=(prop("P-1",identity="5"),prop("P-2",identity="5")),
    )
    a1,a2=artifact("A1","P-1"),artifact("A2","P-2")
    p=plan(d,(a1,a2))
    e=stage(p,d,(a1,a2))
    assert e.status=="STAGED"
    assert len(e.staged_artifacts)==2
    assert e.active_artifacts==(a1,a2)


def test_one_failed_target_discards_all_staged_results_and_preserves_all_prior():
    d=delta(
        before_props=(prop("P-1"),prop("P-2")),
        after_props=(prop("P-1",identity="5"),prop("P-2",identity="5")),
    )
    a1=artifact("A1","P-1",kind="ONE")
    a2=artifact("A2","P-2",kind="TWO")
    p=plan(d,(a1,a2))
    def ok(*args): return "c"*64
    def fail(*args): raise RuntimeError("fixture failure")
    e=stage(
        p,d,(a1,a2),
        refreshers={"ONE":ok,"TWO":fail},
        engine_versions={"ONE":"E2","TWO":"E2"},
        ruleset_versions={"ONE":"R2","TWO":"R2"},
    )
    assert e.status=="FAILED"
    assert e.staged_artifacts==()
    assert e.active_artifacts==(a1,a2)


def test_promotion_changes_only_targeted_artifact_and_preserves_unaffected_hash_identically():
    d=delta(
        before_props=(prop("P-1"),prop("P-2")),
        after_props=(prop("P-1",identity="5"),prop("P-2")),
    )
    a1,a2=artifact("A1","P-1"),artifact("A2","P-2")
    p=plan(d,(a1,a2))
    staged=stage(p,d,(a1,a2))
    promoted=promote_staged_refresh(staged)
    assert promoted.status=="PROMOTED"
    by={x.artifact_id:x for x in promoted.active_artifacts}
    assert by["A1"].artifact_fingerprint!=a1.artifact_fingerprint
    assert by["A1"].artifact_version==2
    assert by["A2"] is a2
    assert by["A2"].artifact_fingerprint==a2.artifact_fingerprint
    assert by["A2"].value_fingerprint==a2.value_fingerprint
    assert by["A2"].lineage_fingerprints==a2.lineage_fingerprints
    assert by["A2"].certification_state==a2.certification_state


def test_promotion_requires_fully_staged_execution():
    d=delta(before_props=(prop(),),after_props=(prop(conflicts=("X",)),))
    a=artifact("A","P-1",domains=("GOVERNANCE",))
    blocked=stage(plan(d,(a,)),d,(a,))
    with pytest.raises(ValueError,match="fully STAGED"):
        promote_staged_refresh(blocked)


def test_promoted_refresh_retains_delta_and_frozen_input_lineage():
    d=delta(before_props=(prop(),),after_props=(prop(identity="5"),))
    a=artifact("A","P-1")
    promoted=promote_staged_refresh(stage(plan(d,(a,)),d,(a,)))
    new=promoted.active_artifacts[0]
    assert d.delta_fingerprint in new.lineage_fingerprints
    assert "f"*64 in new.lineage_fingerprints
    assert a.artifact_fingerprint in new.lineage_fingerprints
    assert new.engine_version=="ENGINE-v2"
    assert new.ruleset_version=="RULES-v2"


def test_same_inputs_produce_same_plan_stage_and_promotion_fingerprints():
    d=delta(before_props=(prop(),),after_props=(prop(identity="5"),))
    a=artifact("A","P-1")
    p1=plan(d,(a,))
    p2=plan(d,(a,))
    e1=stage(p1,d,(a,))
    e2=stage(p2,d,(a,))
    x1=promote_staged_refresh(e1)
    x2=promote_staged_refresh(e2)
    assert p1.plan_fingerprint==p2.plan_fingerprint
    assert e1.execution_fingerprint==e2.execution_fingerprint
    assert x1.execution_fingerprint==x2.execution_fingerprint


def test_no_refresh_proof_exists_for_every_unaffected_artifact():
    d=delta(
        before_props=(prop("P-1"),prop("P-2")),
        after_props=(prop("P-1",identity="5"),prop("P-2")),
    )
    a1,a2=artifact("A1","P-1"),artifact("A2","P-2")
    e=stage(plan(d,(a1,a2)),d,(a1,a2))
    proofs={x.artifact_id:x for x in e.proofs}
    assert proofs["A2"].disposition=="NO_IMPACT"
    assert proofs["A2"].action_taken=="NO_REFRESH_PRESERVED"
    assert proofs["A2"].before_artifact_fingerprint==a2.artifact_fingerprint


def test_module_exposes_no_recommendation_publication_or_m12_execution_api():
    import src.community_temporal_state.impact_refresh as mod
    names=set(dir(mod))
    for forbidden in (
        "recommend_listing_price",
        "send_seller_message",
        "publish_report",
        "execute_listing_action",
        "mutate_m12_execution",
    ):
        assert forbidden not in names
