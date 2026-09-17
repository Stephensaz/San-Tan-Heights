from uuid import uuid4
import pytest
from src.production_certification.models import ProductionCertificationRun, ProductionEvidence, ProductionCheckResult
from src.production_certification.repository import ProductionCertificationRepository

H='a'*64

class Cursor:
    def __init__(self): self.calls=[]; self.row=('row',)
    def execute(self,sql,args): self.calls.append((sql,args))
    def fetchone(self): return self.row


def test_run_requires_sha256_candidate_fingerprint():
    with pytest.raises(ValueError):
        ProductionCertificationRun(uuid4(),uuid4(),'1.0.0','0.1.38','bad','ops')


def test_evidence_is_canonical_json_when_persisted():
    run_id=uuid4(); c=Cursor(); repo=ProductionCertificationRepository()
    ev=ProductionEvidence(uuid4(),run_id,'MANIFEST','contract-manifest',H,'ops',{'z':1,'a':2})
    repo.append_evidence(c,ev)
    assert c.calls[0][1][5] == '{"a":2,"z":1}'


def test_check_status_fails_closed():
    with pytest.raises(ValueError):
        ProductionCheckResult(uuid4(),uuid4(),'ENV','POSTGRES','MAYBE',H,'ops')


def test_repository_anchors_production_run_to_system_certification():
    c=Cursor(); repo=ProductionCertificationRepository()
    run=ProductionCertificationRun(uuid4(),uuid4(),'1.0.0','0.1.38',H,'ops')
    repo.create_run(c,run)
    sql,args=c.calls[0]
    assert 'system_certification_run_id' in sql
    assert args[1] == run.system_certification_run_id
    assert args[4] == H


def test_get_run_is_explicit_by_primary_key():
    c=Cursor(); rid=uuid4(); row=ProductionCertificationRepository().get_run(c,rid)
    assert c.calls[0][1] == (rid,)
    assert row == ('row',)


def test_repository_persists_candidate_manifest_and_environment_evidence():
    from types import SimpleNamespace
    c=Cursor(); repo=ProductionCertificationRepository(); rid=uuid4()
    repo.insert_candidate_freeze(c,SimpleNamespace(production_certification_id=rid,candidate_version='1',candidate_fingerprint=H,artifact_sha256=H,source_revision='r',artifact_uri='u',freeze_fingerprint=H,frozen_by='ops'))
    repo.insert_manifest_pin(c,SimpleNamespace(production_certification_id=rid,manifest_type='BUILD_MANIFEST',manifest_version='1',manifest_sha256=H,manifest_payload={'a':1},pin_fingerprint=H,pinned_by='ops'))
    repo.insert_environment_parity(c,SimpleNamespace(production_certification_id=rid,policy_version='1',expected_fingerprint=H,observed_fingerprint=H,parity_status='PASS',mismatch_keys=(),expected_environment={'a':'1'},observed_environment={'a':'1'},verifier_version='1',verified_by='ops'))
    assert len(c.calls)==3
    assert 'production_candidate_freezes' in c.calls[0][0]
    assert 'production_manifest_pins' in c.calls[1][0]
    assert 'production_environment_parity' in c.calls[2][0]
