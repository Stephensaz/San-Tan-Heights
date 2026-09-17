from datetime import datetime, timezone
from uuid import uuid4
import pytest
from src.production_certification.approval.limited import LimitedApprovalPolicy, LimitedApprovalIssuer
from src.production_certification.shadow.acceptance import ShadowAcceptanceResult
from src.production_certification.go_live.stop_conditions import GoLiveStopResult
P='registries/production-certification/limited-approval-policy.yaml'

def evidence(pc, shadow='PASS', stop='CLEAR'):
    s=ShadowAcceptanceResult(pc,'1.0',shadow,(),(),None,None,'a'*64,'ops')
    g=GoLiveStopResult(pc,'1.0',stop,(),'b'*64,'ops')
    return s,g

def test_limited_approval_is_candidate_and_evidence_bound_and_expires():
    pc=uuid4(); s,g=evidence(pc); now=datetime(2026,9,16,22,0,tzinfo=timezone.utc)
    a=LimitedApprovalIssuer().issue(policy=LimitedApprovalPolicy.load(P),production_certification_id=pc,
      candidate_fingerprint='c'*64,pilot_membership_fingerprint='d'*64,shadow_acceptance=s,stop_conditions=g,approved_by='admin',issued_at=now)
    assert a.approval_type=='LIMITED'
    assert a.max_properties==25
    assert (a.expires_at-a.issued_at).total_seconds()==24*3600
    assert a.shadow_acceptance_fingerprint==s.acceptance_fingerprint
    assert a.stop_condition_fingerprint==g.evidence_fingerprint

def test_limited_approval_cannot_issue_when_shadow_or_stop_gate_fails():
    pc=uuid4(); policy=LimitedApprovalPolicy.load(P)
    s,g=evidence(pc,shadow='FAIL')
    with pytest.raises(ValueError,match='shadow acceptance'):
      LimitedApprovalIssuer().issue(policy=policy,production_certification_id=pc,candidate_fingerprint='c'*64,pilot_membership_fingerprint='d'*64,shadow_acceptance=s,stop_conditions=g,approved_by='admin')
    s,g=evidence(pc,stop='STOP')
    with pytest.raises(ValueError,match='stop conditions'):
      LimitedApprovalIssuer().issue(policy=policy,production_certification_id=pc,candidate_fingerprint='c'*64,pilot_membership_fingerprint='d'*64,shadow_acceptance=s,stop_conditions=g,approved_by='admin')
