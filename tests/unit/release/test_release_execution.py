from types import SimpleNamespace
from uuid import uuid4
import pytest
from src.release.lifecycle import ReleaseItemLifecycle, ReleaseLifecycle
from src.release.validation import ReleaseValidationEngine
from src.release.staging import ReleaseStagingService
from src.release.approval import ReleaseApprovalService
from src.release.rollout import ChunkedPublicationService,PartialFailurePolicyEngine
from src.release.reconciliation import ReleaseReconciliationService
from src.release.rollback import ReleaseRollbackService
from src.release.cancellation import ReleaseCancellationService

class Cursor:
    rowcount=1
    def __init__(self): self.calls=[]
    def execute(self,sql,params=None): self.calls.append((sql,params))

def item(state='PENDING',channel='WEB'):
    return SimpleNamespace(release_item_id=uuid4(),release_id=uuid4(),property_id=uuid4(),report_variant='PUBLIC',channel=channel,membership_ordinal=1,item_state=state,target_snapshot_id=uuid4(),target_report_id=uuid4(),target_render_id=uuid4() if channel else None,target_semantic_fingerprint='a'*64,target_presentation_fingerprint='b'*64 if channel else None)

def test_item_lifecycle_is_guarded_and_audited():
    c=Cursor(); i=item(); r=ReleaseItemLifecycle().transition(c,item=i,to_state='GENERATION_QUEUED')
    assert r.to_state=='GENERATION_QUEUED' and len(c.calls)==2
    with pytest.raises(ValueError): ReleaseItemLifecycle().transition(c,item=i,to_state='PUBLISHED')

def test_release_parent_lifecycle_is_guarded():
    c=Cursor(); rel=SimpleNamespace(release_id=uuid4(),release_state='DRAFT')
    assert ReleaseLifecycle().transition(c,release=rel,to_state='ASSEMBLING').to_state=='ASSEMBLING'
    with pytest.raises(ValueError): ReleaseLifecycle().transition(c,release=rel,to_state='PUBLISHED')

def test_validation_requires_exact_presentation_target_for_channel_member():
    e=ReleaseValidationEngine(); bad=item(); bad.target_render_id=None
    assert e.validate_item(bad).reason_code=='TARGET_RENDER_MISSING'
    assert e.validate_item(item()).status=='PASS'
    assert e.validate_item(item(channel=None)).status=='PASS'

def test_staging_requires_all_validated():
    class L:
        def __init__(self):self.calls=[]
        def transition(self,*a,**k):self.calls.append(k)
    l=L(); s=ReleaseStagingService(lifecycle=l)
    assert s.stage(Cursor(),items=[item('VALIDATED')])==1
    with pytest.raises(ValueError):s.stage(Cursor(),items=[item('GENERATED')])

def test_approval_requires_frozen_manifest_and_staged_items():
    class L:
        def transition(self,*a,**k):pass
    rel=SimpleNamespace(release_id=uuid4(),manifest_fingerprint='c'*64)
    assert ReleaseApprovalService(lifecycle=L()).approve(Cursor(),release=rel,items=[item('STAGED')],approved_by='OPS')=='APPROVED'
    rel2=SimpleNamespace(release_id=uuid4(),manifest_fingerprint=None)
    with pytest.raises(ValueError):ReleaseApprovalService(lifecycle=L()).approve(Cursor(),release=rel2,items=[item('STAGED')],approved_by='OPS')

def test_chunked_publication_halts_under_strict_failure_policy():
    class L:
        def transition(self,*a,**k):pass
    calls=[]
    def pub(c,i): calls.append(i); return SimpleNamespace(status='BLOCKED',reason_code='X')
    svc=ChunkedPublicationService(lifecycle=L(),publish_item=pub,policy_engine=PartialFailurePolicyEngine(),chunk_size=1)
    out=svc.publish(Cursor(),items=[item('APPROVED'),item('APPROVED')])
    assert out=={'published':0,'failed':1,'halted':True} and len(calls)==1

def test_reconciliation_detects_exact_total_and_partial_failure():
    rel=SimpleNamespace(total_item_count=2)
    r=ReleaseReconciliationService().reconcile(release=rel,items=[item('PUBLISHED'),item('FAILED')])
    assert r.status=='PARTIAL_FAILURE'
    r2=ReleaseReconciliationService().reconcile(release=rel,items=[item('PUBLISHED')])
    assert r2.status=='MISMATCH'

def test_rollback_runs_published_items_reverse_membership_order():
    class L:
        def transition(self,*a,**k):pass
    a=item('PUBLISHED'); b=item('PUBLISHED'); a.membership_ordinal=1;b.membership_ordinal=2
    order=[]
    def rb(c,i):order.append(i.membership_ordinal);return SimpleNamespace(status='ROLLED_BACK')
    assert ReleaseRollbackService(lifecycle=L(),rollback_item=rb).rollback(Cursor(),items=[a,b])==2
    assert order==[2,1]

def test_cancellation_rejects_release_with_publication_activity():
    class L:
        def transition(self,*a,**k):pass
    s=ReleaseCancellationService(lifecycle=L())
    assert s.cancel(Cursor(),items=[item('STAGED')])==1
    with pytest.raises(ValueError):s.cancel(Cursor(),items=[item('PUBLISHED')])
