from datetime import datetime, timezone
from uuid import UUID, uuid4

from src.production_certification.approval.limited import LimitedApproval
from src.production_certification.cohort.deployment import Cohort25DeploymentService
from src.production_certification.cohort.membership import CohortMembershipFreezer, CohortRegistry
from src.production_certification.go_live.stop_conditions import GoLiveStopResult
from src.production_certification.pilot.eligibility import PilotEligibilityResult

NOW=datetime(2026,9,16,22,0,tzinfo=timezone.utc)


def setup_membership():
    pc=uuid4(); p=PilotEligibilityResult('1.0.0',tuple(UUID(int=i+1) for i in range(30)),(),'e'*64)
    a=LimitedApproval(uuid4(),pc,'1.0.0','c'*64,p.membership_fingerprint,25,('AGENT','SELLER','PUBLIC'),'a'*64,'b'*64,
        NOW.replace(hour=21),NOW.replace(day=17,hour=21),'d'*64,'admin')
    m=CohortMembershipFreezer().freeze(registry=CohortRegistry.load('registries/production-certification/cohort-policy.yaml'),
        cohort_code='COHORT_25',pilot=p,approval=a,candidate_fingerprint='c'*64,frozen_by='ops',frozen_at=NOW)
    stop=GoLiveStopResult(pc,'1.0.0','CLEAR',(),'f'*64,'ops')
    return m,a,stop


class Executor:
    def __init__(self, fail_on=None): self.fail_on=fail_on; self.calls=[]
    def deploy(self, *, property_id, variants, candidate_fingerprint):
        self.calls.append(property_id)
        if self.fail_on==property_id: raise RuntimeError('activation failed')
        return {'variants':list(variants),'candidate_fingerprint':candidate_fingerprint}


def test_cohort_25_deploys_only_frozen_members_and_all_25_on_success():
    m,a,stop=setup_membership(); ex=Executor()
    d=Cohort25DeploymentService().deploy(membership=m,approval=a,current_stop_conditions=stop,executor=ex,deployed_by='ops',started_at=NOW)
    assert d.deployment_status=='PASS'
    assert tuple(ex.calls)==m.property_ids
    assert len(d.items)==25 and all(x.status=='PASS' for x in d.items)


def test_cohort_25_fail_fast_prevents_later_activation():
    m,a,stop=setup_membership(); failed=m.property_ids[6]; ex=Executor(fail_on=failed)
    d=Cohort25DeploymentService().deploy(membership=m,approval=a,current_stop_conditions=stop,executor=ex,deployed_by='ops',started_at=NOW)
    assert d.deployment_status=='FAIL'
    assert len(d.items)==7
    assert ex.calls[-1]==failed
    assert m.property_ids[7] not in ex.calls
