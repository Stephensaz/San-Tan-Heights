from dataclasses import replace
from uuid import UUID
from src.snapshot.findings.freezer import FindingFreezer
from src.snapshot.fingerprints import SnapshotFingerprintEngine
from src.snapshot.governed_state.models import GovernedDependency
from tests.unit.snapshot._fixtures import finding

PID=UUID("11111111-1111-1111-1111-111111111111")


def _f(fid, scope, fpchar):
    frozen = FindingFreezer().freeze((finding(fid=fid),))[0]
    return replace(frozen, publication_scope=scope, semantic_fingerprint=fpchar*64)


def _d(did, variants, fpchar):
    return GovernedDependency("TEST_DEP", did, fpchar*64, "f"*64, "1", True, tuple(variants))


def _calc(findings, deps):
    return SnapshotFingerprintEngine().calculate(
        property_id=PID,
        intelligence_schema_version="intel-1",
        governance_schema_version="gov-1",
        findings=tuple(findings),
        dependencies=tuple(deps),
    )


def test_snapshot_fingerprints_are_order_independent():
    f1=_f("f1","ALL","a"); f2=_f("f2","AGENT","b")
    d1=_d("d1",("AGENT","SELLER","PUBLIC"),"c"); d2=_d("d2",("AGENT",),"d")
    assert _calc((f1,f2),(d1,d2)) == _calc((f2,f1),(d2,d1))


def test_agent_only_change_leaves_seller_and_public_unchanged():
    shared=_f("shared","ALL","a")
    agent=_f("agent","AGENT","b")
    dep=_d("shared",("AGENT","SELLER","PUBLIC"),"c")
    before=_calc((shared,agent),(dep,))
    after=_calc((shared,replace(agent, semantic_fingerprint="e"*64)),(dep,))
    assert before.semantic_fingerprint != after.semantic_fingerprint
    assert before.agent_semantic_fingerprint != after.agent_semantic_fingerprint
    assert before.seller_semantic_fingerprint == after.seller_semantic_fingerprint
    assert before.public_semantic_fingerprint == after.public_semantic_fingerprint


def test_public_change_only_changes_public_when_scope_is_public_only():
    public=_f("public","PUBLIC","a")
    before=_calc((public,),())
    after=_calc((replace(public, semantic_fingerprint="b"*64),),())
    assert before.public_semantic_fingerprint != after.public_semantic_fingerprint
    assert before.agent_semantic_fingerprint == after.agent_semantic_fingerprint
    assert before.seller_semantic_fingerprint == after.seller_semantic_fingerprint


def test_shared_dependency_change_changes_all_variants():
    dep=_d("shared",("AGENT","SELLER","PUBLIC"),"a")
    before=_calc((),(dep,))
    after=_calc((),(replace(dep, semantic_fingerprint="b"*64),))
    assert before.agent_semantic_fingerprint != after.agent_semantic_fingerprint
    assert before.seller_semantic_fingerprint != after.seller_semantic_fingerprint
    assert before.public_semantic_fingerprint != after.public_semantic_fingerprint
