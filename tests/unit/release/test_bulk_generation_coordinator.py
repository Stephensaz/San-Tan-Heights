from types import SimpleNamespace
from uuid import uuid4
from src.release.generation import BulkGenerationCoordinator

class Lifecycle:
    def __init__(self):self.calls=[]
    def transition(self,*a,**k):self.calls.append(k)
class Cursor: pass

def make(state='PENDING',channel='WEB'):
    return SimpleNamespace(release_item_id=uuid4(),release_id=uuid4(),property_id=uuid4(),report_variant='PUBLIC',channel=channel,membership_ordinal=1,item_state=state)

def test_bulk_generation_queues_report_and_channel_render_without_mutating_membership():
    l=Lifecycle(); q=[]; r=[]
    svc=BulkGenerationCoordinator(lifecycle=l,queue_report=lambda c,i:q.append(i.release_item_id),queue_render=lambda c,i:r.append(i.release_item_id))
    i=make(); before=(i.property_id,i.report_variant,i.channel,i.membership_ordinal)
    out=svc.coordinate(Cursor(),items=[i])
    assert out['queued']==(i.release_item_id,)
    assert q==[i.release_item_id] and r==[i.release_item_id]
    assert before==(i.property_id,i.report_variant,i.channel,i.membership_ordinal)

def test_semantic_only_member_does_not_require_render_queue():
    l=Lifecycle(); q=[]; r=[]; i=make(channel=None)
    out=BulkGenerationCoordinator(lifecycle=l,queue_report=lambda c,x:q.append(x.release_item_id),queue_render=lambda c,x:r.append(x.release_item_id)).coordinate(Cursor(),items=[i])
    assert out['queued']==(i.release_item_id,) and r==[]
