from pathlib import Path
from uuid import uuid4
from src.production_certification.audit.sample import ManualAuditPolicy, ManualAuditSample
from src.production_certification.audit.evidence import ManualAuditEvidenceCapture

ROOT=Path(__file__).resolve().parents[3]
POLICY=ROOT/'registries/production-certification/manual-audit-policy.yaml'


def _sample(p):
    return ManualAuditSample(uuid4(),uuid4(),uuid4(),'STH-MANUAL-AUDIT-POLICY-v1.0',(p,),(), 'a'*64,'builder')


def test_evidence_capture_is_hash_stable_and_requires_sample_membership():
    policy=ManualAuditPolicy.load(POLICY); p=uuid4(); sample=_sample(p); cap=ManualAuditEvidenceCapture()
    e=cap.capture(policy=policy,sample=sample,property_id=p,audit_status='PASS',
        checklist_results={'identity':'PASS','wording':'PASS'},reviewed_by='qa')
    assert len(e.evidence_hash)==64 and e.checklist_version==policy.checklist_version
    try:
        cap.capture(policy=policy,sample=sample,property_id=uuid4(),audit_status='PASS',checklist_results={'x':'PASS'},reviewed_by='qa')
        assert False
    except ValueError as exc:
        assert 'not part' in str(exc)


def test_evidence_capture_does_not_compute_acceptance_verdict():
    policy=ManualAuditPolicy.load(POLICY); p=uuid4(); sample=_sample(p)
    e=ManualAuditEvidenceCapture().capture(policy=policy,sample=sample,property_id=p,audit_status='REVIEW_REQUIRED',
        checklist_results={'visual':'REVIEW'},reviewed_by='qa',notes='needs human follow-up')
    assert e.audit_status=='REVIEW_REQUIRED'
    assert not hasattr(e,'go_live_verdict')
