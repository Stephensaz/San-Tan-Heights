from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4
import pytest

from src.production_certification.go_live.publication_control import (
    ManualPublicationAuthorizer, ManualPublicationPolicy,
    ProgressiveAutomationAuthorizer, ProgressiveAutomationPolicy,
    PublicationPointerState, RollbackBaselineCapture,
)
from src.production_certification.go_live.stop_conditions import GoLiveStopResult

ROOT=Path(__file__).resolve().parents[3]
MANUAL=ROOT/'registries/production-certification/manual-publication-policy.yaml'
AUTO=ROOT/'registries/production-certification/progressive-automation-policy.yaml'

def clear(pc):
    return GoLiveStopResult(pc,'1.0.0','CLEAR',(), 'a'*64,'ops')

def stop(pc):
    return GoLiveStopResult(pc,'1.0.0','STOP',('OPEN_CRITICAL_INCIDENT',), 'b'*64,'ops')

def test_manual_publication_policy_and_authorization():
    p=ManualPublicationPolicy.load(MANUAL); pc=uuid4(); now=datetime.now(timezone.utc)
    a=ManualPublicationAuthorizer().authorize(policy=p,production_certification_id=pc,action='PUBLISH',
        expected_candidate_fingerprint='c'*64,observed_candidate_fingerprint='c'*64,
        current_stop_conditions=clear(pc),operator_id='operator-1',reason_code='GO_LIVE_MANUAL',authorized_at=now)
    assert a.mode=='MANUAL' and len(a.authorization_fingerprint)==64

def test_manual_publication_rejects_drift_and_stop():
    p=ManualPublicationPolicy.load(MANUAL); pc=uuid4()
    with pytest.raises(ValueError,match='candidate fingerprint mismatch'):
        ManualPublicationAuthorizer().authorize(policy=p,production_certification_id=pc,action='PUBLISH',
          expected_candidate_fingerprint='c'*64,observed_candidate_fingerprint='d'*64,
          current_stop_conditions=clear(pc),operator_id='op',reason_code='R')
    with pytest.raises(ValueError,match='not clear'):
        ManualPublicationAuthorizer().authorize(policy=p,production_certification_id=pc,action='PUBLISH',
          expected_candidate_fingerprint='c'*64,observed_candidate_fingerprint='c'*64,
          current_stop_conditions=stop(pc),operator_id='op',reason_code='R')

def test_progressive_automation_requires_prior_pass_and_clear():
    p=ProgressiveAutomationPolicy.load(AUTO); pc=uuid4(); cert=uuid4()
    svc=ProgressiveAutomationAuthorizer()
    h=svc.authorize(policy=p,production_certification_id=pc,stage_code='COHORT_100',candidate_fingerprint='c'*64,
      prior_stage='COHORT_25',prior_certification_id=cert,prior_certification_fingerprint='d'*64,
      prior_certification_status='PASS',current_stop_conditions=clear(pc),requested_by='ops',reason_code='EXPAND')
    assert h.stage_code=='COHORT_100' and h.mode=='AUTOMATED'
    with pytest.raises(ValueError,match='has not passed'):
      svc.authorize(policy=p,production_certification_id=pc,stage_code='COHORT_100',candidate_fingerprint='c'*64,
        prior_stage='COHORT_25',prior_certification_id=cert,prior_certification_fingerprint='d'*64,
        prior_certification_status='FAIL',current_stop_conditions=clear(pc),requested_by='ops',reason_code='EXPAND')
    with pytest.raises(ValueError,match='not clear'):
      svc.authorize(policy=p,production_certification_id=pc,stage_code='COHORT_100',candidate_fingerprint='c'*64,
        prior_stage='COHORT_25',prior_certification_id=cert,prior_certification_fingerprint='d'*64,
        prior_certification_status='PASS',current_stop_conditions=stop(pc),requested_by='ops',reason_code='EXPAND')

def test_rollback_baseline_is_deterministic_and_complete():
    p=ProgressiveAutomationPolicy.load(AUTO); pc=uuid4(); cert=uuid4()
    h=ProgressiveAutomationAuthorizer().authorize(policy=p,production_certification_id=pc,stage_code='COHORT_100',
      candidate_fingerprint='c'*64,prior_stage='COHORT_25',prior_certification_id=cert,
      prior_certification_fingerprint='d'*64,prior_certification_status='PASS',current_stop_conditions=clear(pc),
      requested_by='ops',reason_code='EXPAND',created_at=datetime(2026,9,16,tzinfo=timezone.utc),automation_handoff_id=uuid4())
    props=[uuid4(),uuid4()]
    states=[
      PublicationPointerState(props[1],'PUBLIC','WEB',uuid4(),uuid4()),
      PublicationPointerState(props[0],'PUBLIC','WEB',uuid4(),uuid4()),
    ]
    cap=RollbackBaselineCapture()
    bid=uuid4(); when=datetime(2026,9,16,1,tzinfo=timezone.utc)
    a=cap.capture(production_certification_id=pc,stage_code='COHORT_100',candidate_fingerprint='c'*64,handoff=h,
      target_property_ids=props,pointer_states=states,captured_by='ops',captured_at=when,rollback_baseline_id=bid)
    b=cap.capture(production_certification_id=pc,stage_code='COHORT_100',candidate_fingerprint='c'*64,handoff=h,
      target_property_ids=reversed(props),pointer_states=reversed(states),captured_by='ops',captured_at=when,rollback_baseline_id=bid)
    assert a.baseline_fingerprint==b.baseline_fingerprint
    assert tuple(x.property_id for x in a.entries)==tuple(sorted(props,key=str))

def test_rollback_baseline_rejects_missing_target():
    p=ProgressiveAutomationPolicy.load(AUTO); pc=uuid4(); cert=uuid4()
    h=ProgressiveAutomationAuthorizer().authorize(policy=p,production_certification_id=pc,stage_code='COHORT_100',
      candidate_fingerprint='c'*64,prior_stage='COHORT_25',prior_certification_id=cert,
      prior_certification_fingerprint='d'*64,prior_certification_status='PASS',current_stop_conditions=clear(pc),
      requested_by='ops',reason_code='EXPAND')
    p1,p2=uuid4(),uuid4()
    with pytest.raises(ValueError,match='missing target properties'):
      RollbackBaselineCapture().capture(production_certification_id=pc,stage_code='COHORT_100',candidate_fingerprint='c'*64,
        handoff=h,target_property_ids=(p1,p2),pointer_states=(PublicationPointerState(p1,'PUBLIC','WEB',None,None),),captured_by='ops')
