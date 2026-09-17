from dataclasses import replace
from datetime import datetime, timezone
from uuid import UUID, uuid4

from src.production_certification.approval.limited import LimitedApproval
from src.production_certification.cohort.certification import CohortEvidenceCertifier, CohortEvidencePolicy
from src.production_certification.cohort.deployment import Cohort25DeploymentService
from src.production_certification.cohort.membership import CohortMembershipFreezer, CohortRegistry
from src.production_certification.go_live.stop_conditions import GoLiveStopResult
from src.production_certification.pilot.eligibility import PilotEligibilityResult

NOW=datetime(2026,9,16,22,0,tzinfo=timezone.utc)
P='registries/production-certification/cohort-evidence-certification.yaml'

class Ex:
    def __init__(self,fail=False): self.n=0; self.fail=fail
    def deploy(self, **kwargs):
        self.n+=1
        if self.fail and self.n==5: raise RuntimeError('boom')
        return {'ok':True}

def setup(fail=False):
    pc=uuid4(); p=PilotEligibilityResult('1.0.0',tuple(UUID(int=i+1) for i in range(30)),(),'e'*64)
    a=LimitedApproval(uuid4(),pc,'1.0.0','c'*64,p.membership_fingerprint,25,('AGENT','SELLER','PUBLIC'),'a'*64,'b'*64,
      NOW.replace(hour=21),NOW.replace(day=17,hour=21),'d'*64,'admin')
    m=CohortMembershipFreezer().freeze(registry=CohortRegistry.load('registries/production-certification/cohort-policy.yaml'),cohort_code='COHORT_25',pilot=p,approval=a,candidate_fingerprint='c'*64,frozen_by='ops',frozen_at=NOW)
    d=Cohort25DeploymentService().deploy(membership=m,approval=a,current_stop_conditions=GoLiveStopResult(pc,'1','CLEAR',(),'f'*64,'ops'),executor=Ex(fail),deployed_by='ops',started_at=NOW)
    return m,d


def test_cohort_evidence_certifies_only_complete_passing_deployment():
    m,d=setup(False)
    r=CohortEvidenceCertifier().certify(policy=CohortEvidencePolicy.load(P),membership=m,deployment=d,certified_by='auditor')
    assert r.certification_status=='PASS'
    assert r.expected_item_count==r.deployed_item_count==r.passed_item_count==25


def test_cohort_evidence_fails_incomplete_or_fingerprint_drift():
    m,d=setup(True)
    r=CohortEvidenceCertifier().certify(policy=CohortEvidencePolicy.load(P),membership=m,deployment=d,certified_by='auditor')
    assert r.certification_status=='FAIL'
    assert 'DEPLOYED_ITEM_COUNT_MISMATCH' in r.reason_codes
    m2,d2=setup(False)
    drift=replace(d2,membership_fingerprint='0'*64)
    r2=CohortEvidenceCertifier().certify(policy=CohortEvidencePolicy.load(P),membership=m2,deployment=drift,certified_by='auditor')
    assert r2.certification_status=='FAIL'
    assert 'MEMBERSHIP_FINGERPRINT_MISMATCH' in r2.reason_codes
