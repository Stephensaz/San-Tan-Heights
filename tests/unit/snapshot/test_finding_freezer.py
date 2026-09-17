import pytest
from src.snapshot.findings import FindingFreezer, FindingFreezeError
from tests.unit.snapshot._fixtures import finding

def test_freezes_only_production_ready_and_preserves_governed_values():
    good=finding(value={'code':'COMMON_AREA'})
    blocked=finding('f2','CORNER_STATUS','BLOCKED')
    out=FindingFreezer().freeze((blocked,good))
    assert len(out)==1
    f=out[0]
    assert f.finding_id==good.finding_id
    assert f.canonical_value==good.canonical_value
    assert f.agent_wording==good.approved_wording['agent']
    assert f.publication_scope==good.publication_scope
    assert f.semantic_fingerprint==good.semantic_fingerprint

def test_internal_only_not_promoted_to_snapshot_finding():
    assert FindingFreezer().freeze((finding(status='INTERNAL_ONLY'),)) == ()

def test_production_ready_requires_pass_qa():
    with pytest.raises(FindingFreezeError): FindingFreezer().freeze((finding(qa='REVIEW_REQUIRED'),))

def test_duplicate_finding_id_fails_closed():
    with pytest.raises(FindingFreezeError): FindingFreezer().freeze((finding('same'),finding('same','CORNER_STATUS')))
