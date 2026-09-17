from datetime import datetime, timezone
from uuid import UUID, uuid4
import pytest

from src.production_certification.approval.limited import LimitedApproval
from src.production_certification.cohort.membership import CohortMembershipFreezer, CohortRegistry
from src.production_certification.pilot.eligibility import PilotEligibilityResult

P='registries/production-certification/cohort-policy.yaml'
NOW=datetime(2026,9,16,22,0,tzinfo=timezone.utc)


def approval(pc, pilot_fp):
    return LimitedApproval(uuid4(),pc,'1.0.0','c'*64,pilot_fp,25,('AGENT','SELLER','PUBLIC'),'a'*64,'b'*64,
        NOW.replace(hour=21),NOW.replace(day=17,hour=21),'d'*64,'admin')


def pilot(count=30):
    ids=tuple(UUID(int=i+1) for i in range(count))
    return PilotEligibilityResult('1.0.0',ids,(), 'e'*64)


def test_cohort_25_freeze_is_exact_deterministic_and_approval_bound():
    pc=uuid4(); p=pilot(); a=approval(pc,p.membership_fingerprint); registry=CohortRegistry.load(P); cid=uuid4()
    x=CohortMembershipFreezer().freeze(registry=registry,cohort_code='COHORT_25',pilot=p,approval=a,
        candidate_fingerprint='c'*64,frozen_by='ops',frozen_at=NOW,cohort_id=cid)
    y=CohortMembershipFreezer().freeze(registry=registry,cohort_code='COHORT_25',pilot=p,approval=a,
        candidate_fingerprint='c'*64,frozen_by='ops',frozen_at=NOW,cohort_id=cid)
    assert len(x.property_ids)==25
    assert x.property_ids==p.selected_property_ids[:25]
    assert x.membership_fingerprint==y.membership_fingerprint
    assert x.limited_approval_fingerprint==a.approval_fingerprint


def test_cohort_freeze_rejects_insufficient_population_and_candidate_drift():
    pc=uuid4(); registry=CohortRegistry.load(P); p=pilot(24); a=approval(pc,p.membership_fingerprint)
    with pytest.raises(ValueError,match='insufficient'):
        CohortMembershipFreezer().freeze(registry=registry,cohort_code='COHORT_25',pilot=p,approval=a,
            candidate_fingerprint='c'*64,frozen_by='ops',frozen_at=NOW)
    p=pilot(); a=approval(pc,p.membership_fingerprint)
    with pytest.raises(ValueError,match='candidate fingerprint'):
        CohortMembershipFreezer().freeze(registry=registry,cohort_code='COHORT_25',pilot=p,approval=a,
            candidate_fingerprint='f'*64,frozen_by='ops',frozen_at=NOW)
