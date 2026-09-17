from datetime import datetime, timezone
from uuid import UUID
import pytest

from src.production_certification.go_live.finalization import (
    CertificationEvidenceBundleBuilder, CertificationEvidenceItem, CertificationRevocationService,
    CohortRollbackContainmentService, FullApprovalIssuer, FullApprovalPolicy,
)
from src.production_certification.go_live.publication_control import RollbackBaseline, RollbackBaselineEntry
from src.production_certification.go_live.stop_conditions import GoLiveStopResult

NOW=datetime(2026,9,16,23,30,tzinfo=timezone.utc)
PC=UUID(int=9100); CAND='c'*64


def baseline():
    entries=tuple(RollbackBaselineEntry(UUID(int=i), 'PUBLIC','WEB', UUID(int=100+i), UUID(int=200+i), chr(96+i)*64) for i in (1,2,3))
    return RollbackBaseline(UUID(int=1),PC,'COHORT_100',CAND,UUID(int=2),'h'*64,entries,'b'*64,'ops',NOW)

class Executor:
    def __init__(self, fail=None): self.fail=fail; self.restored=[]; self.contained=[]
    def restore(self, *, entry):
        self.restored.append(entry.property_id)
        if entry.property_id==self.fail: raise RuntimeError('restore failed')
        return {'restored': True}
    def contain(self, *, property_id, reason_code):
        self.contained.append(property_id); return {'frozen': True, 'reason_code': reason_code}

def stop(status='CLEAR'):
    return GoLiveStopResult(PC,'1.0.0',status,() if status=='CLEAR' else ('X',),'s'*64,'ops')

def bundle():
    policy=FullApprovalPolicy.load('registries/production-certification/full-approval-policy.yaml')
    items=[CertificationEvidenceItem(code, hex(i+1)[2:]*64 if len(hex(i+1)[2:])==1 else 'a'*64) for i,code in enumerate(policy.required_evidence_codes)]
    # normalize fingerprints simply for test validity
    items=[CertificationEvidenceItem(x.evidence_code, chr(97+(i%6))*64) for i,x in enumerate(items)]
    return policy, CertificationEvidenceBundleBuilder().build(production_certification_id=PC,candidate_fingerprint=CAND,
        required_codes=policy.required_evidence_codes,items=items,built_by='cert',built_at=NOW)

def test_rollback_runs_reverse_and_contains_failure():
    ex=Executor(fail=UUID(int=2))
    result=CohortRollbackContainmentService().execute(baseline=baseline(),candidate_fingerprint=CAND,executor=ex,
        executed_by='ops',reason_code='ROLLOUT_FAILURE',executed_at=NOW)
    assert ex.restored == [UUID(int=3),UUID(int=2),UUID(int=1)]
    assert ex.contained == [UUID(int=2)]
    assert result.status == 'CONTAINED'

def test_evidence_bundle_requires_every_required_pass_item():
    with pytest.raises(ValueError, match='missing required'):
        CertificationEvidenceBundleBuilder().build(production_certification_id=PC,candidate_fingerprint=CAND,
            required_codes=('A','B'),items=(CertificationEvidenceItem('A','a'*64),),built_by='cert',built_at=NOW)

def test_revocation_is_candidate_bound():
    _,b=bundle()
    with pytest.raises(ValueError, match='candidate mismatch'):
        CertificationRevocationService().revoke(bundle=b,candidate_fingerprint='d'*64,reason_code='INCIDENT',detail='x',revoked_by='admin',revoked_at=NOW)

def test_full_approval_requires_clear_stop_all_rollout_pass_and_no_revocation():
    policy,b=bundle()
    certs={stage:('PASS', chr(97+i)*64) for i,stage in enumerate(policy.required_rollout_stages)}
    approval=FullApprovalIssuer().issue(policy=policy,bundle=b,candidate_fingerprint=CAND,stop_conditions=stop(),
        rollout_stage_certifications=certs,active_revocations=(),approved_by='admin',approved_at=NOW)
    assert approval.approval_type == 'FULL_APPROVAL'
    assert approval.candidate_fingerprint == CAND

def test_full_approval_denied_if_revoked_or_stop_active():
    policy,b=bundle(); svc=CertificationRevocationService()
    rev=svc.revoke(bundle=b,candidate_fingerprint=CAND,reason_code='INCIDENT',detail='unsafe',revoked_by='admin',revoked_at=NOW)
    certs={stage:('PASS', chr(97+i)*64) for i,stage in enumerate(policy.required_rollout_stages)}
    with pytest.raises(ValueError, match='revoked'):
        FullApprovalIssuer().issue(policy=policy,bundle=b,candidate_fingerprint=CAND,stop_conditions=stop(),rollout_stage_certifications=certs,active_revocations=(rev,),approved_by='admin',approved_at=NOW)
    with pytest.raises(ValueError, match='not clear'):
        FullApprovalIssuer().issue(policy=policy,bundle=b,candidate_fingerprint=CAND,stop_conditions=stop('STOP'),rollout_stage_certifications=certs,active_revocations=(),approved_by='admin',approved_at=NOW)
