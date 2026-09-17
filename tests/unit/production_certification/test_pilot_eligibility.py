from pathlib import Path
from uuid import uuid4
from src.production_certification.pilot.eligibility import PilotEligibilityPolicy,PilotPropertyCandidate,RealPropertyPilotEligibilityResolver
ROOT=Path(__file__).resolve().parents[3]; POLICY=ROOT/'registries/production-certification/pilot-eligibility.yaml'
def C(pid, **kw):
    d=dict(identity_status='RESOLVED',snapshot_id=uuid4(),snapshot_qa_status='PASS',snapshot_completeness='COMPLETE',open_incident_severities=(),publication_frozen=False); d.update(kw)
    return PilotPropertyCandidate(pid,**d)
def test_pilot_selection_is_deterministic_and_clean_only():
    p=PilotEligibilityPolicy.load(POLICY); a,b,c=uuid4(),uuid4(),uuid4()
    r1=RealPropertyPilotEligibilityResolver().resolve(policy=p,candidates=[C(c),C(a),C(b,open_incident_severities=('CRITICAL',))])
    r2=RealPropertyPilotEligibilityResolver().resolve(policy=p,candidates=[C(a),C(b,open_incident_severities=('CRITICAL',)),C(c)])
    assert r1.selected_property_ids==r2.selected_property_ids
    assert r1.membership_fingerprint==r2.membership_fingerprint
    assert b not in r1.selected_property_ids

def test_pilot_blocks_unresolved_identity_bad_snapshot_and_freeze():
    p=PilotEligibilityPolicy.load(POLICY); x=uuid4()
    r=RealPropertyPilotEligibilityResolver().resolve(policy=p,candidates=[C(x,identity_status='BLOCKED',snapshot_qa_status='FAIL',publication_frozen=True)])
    d=r.decisions[0]
    assert not d.eligible and {'IDENTITY_NOT_RESOLVED','SNAPSHOT_QA_NOT_PASS','PUBLICATION_FROZEN'} <= set(d.reason_codes)

def test_pilot_cap_is_explicit_and_reproducible():
    p=PilotEligibilityPolicy('1','RESOLVED','PASS',('COMPLETE',),('CRITICAL',),True,1,('PUBLIC',))
    ids=sorted([uuid4(),uuid4()],key=str)
    r=RealPropertyPilotEligibilityResolver().resolve(policy=p,candidates=[C(ids[1]),C(ids[0])])
    assert r.selected_property_ids==(ids[0],)
    assert any(d.reason_codes==('PILOT_CAP_EXCEEDED',) for d in r.decisions)
