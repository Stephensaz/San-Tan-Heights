from uuid import uuid4
from src.production_certification.shadow.acceptance import ShadowAcceptancePolicy, ShadowAcceptanceEngine
from src.production_certification.shadow.tracking import ShadowCycleEvidence
from src.production_certification.audit.sample import ManualAuditSample
from src.production_certification.audit.evidence import ManualAuditEvidence

POLICY='registries/production-certification/shadow-acceptance-policy.yaml'
H='a'*64

def cycle(pc, n, membership, status='PASS'):
    failed=0 if status=='PASS' else 1
    return ShadowCycleEvidence(uuid4(),pc,n,'1.0.0',membership,1,1-failed,failed,status,H,H,'tester',())

def test_three_latest_pass_cycles_and_complete_pass_audit_are_accepted():
    pc=uuid4(); membership='b'*64
    cycles=[cycle(pc,i,membership) for i in (1,2,3)]
    p1,p2=uuid4(),uuid4(); sid=uuid4()
    sample=ManualAuditSample(sid,pc,cycles[-1].shadow_cycle_id,'v1',(p1,p2),(),H,'builder')
    evidence=(ManualAuditEvidence(uuid4(),sid,p1,'PASS','c',{'ok':True},None,'c'*64,'r'),
              ManualAuditEvidence(uuid4(),sid,p2,'PASS','c',{'ok':True},None,'d'*64,'r'))
    result=ShadowAcceptanceEngine().evaluate(policy=ShadowAcceptancePolicy.load(POLICY),production_certification_id=pc,
        pilot_membership_fingerprint=membership,cycles=cycles,manual_audit_sample=sample,manual_audit_evidence=evidence,evaluated_by='ops')
    assert result.status=='PASS'
    assert result.reason_codes==()
    assert result.accepted_cycle_ids==tuple(x.shadow_cycle_id for x in cycles)

def test_failed_latest_cycle_breaks_consecutive_acceptance():
    pc=uuid4(); membership='b'*64
    cycles=[cycle(pc,1,membership),cycle(pc,2,membership),cycle(pc,3,membership,'FAIL')]
    result=ShadowAcceptanceEngine().evaluate(policy=ShadowAcceptancePolicy.load(POLICY),production_certification_id=pc,
        pilot_membership_fingerprint=membership,cycles=cycles,manual_audit_sample=None,manual_audit_evidence=(),evaluated_by='ops')
    assert result.status=='FAIL'
    assert 'INSUFFICIENT_CONSECUTIVE_PASS_CYCLES' in result.reason_codes

def test_membership_drift_and_review_required_fail_acceptance():
    pc=uuid4(); membership='b'*64
    cycles=[cycle(pc,1,membership),cycle(pc,2,membership),cycle(pc,3,'e'*64)]
    p=uuid4(); sid=uuid4(); sample=ManualAuditSample(sid,pc,cycles[-1].shadow_cycle_id,'v1',(p,),(),H,'builder')
    ev=(ManualAuditEvidence(uuid4(),sid,p,'REVIEW_REQUIRED','c',{'ok':False},None,'f'*64,'r'),)
    r=ShadowAcceptanceEngine().evaluate(policy=ShadowAcceptancePolicy.load(POLICY),production_certification_id=pc,
      pilot_membership_fingerprint=membership,cycles=cycles,manual_audit_sample=sample,manual_audit_evidence=ev,evaluated_by='ops')
    assert r.status=='FAIL'
    assert 'SHADOW_MEMBERSHIP_DRIFT' in r.reason_codes
    assert 'MANUAL_AUDIT_NOT_ALL_PASS' in r.reason_codes
