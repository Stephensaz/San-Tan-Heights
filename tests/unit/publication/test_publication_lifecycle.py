from types import SimpleNamespace as NS
from uuid import uuid4
from src.publication.lifecycle import ControlledPublicationLifecycle
from src.publication.history import PublicationHistoryService
from src.publication.repository import PublicationHistoryRecord

class Repo:
    def __init__(self):
        self.current={}; self.channels={}; self.history=[]; self.locks=[]; self.published=set()
    def lock_target(self,c,p,v,ch): self.locks.append((p,v,ch))
    def lock_semantic_target(self,c,p,v): self.locks.append((p,v,'SEMANTIC'))
    def get_current_report(self,c,p,v): return self.current.get((p,v))
    def set_current_report(self,c,p): self.current[(p.property_id,p.report_variant)]=(p.report_id,p.pointer_version)
    def clear_current_report(self,c,p,v): self.current.pop((p,v),None)
    def get_channel_pointer(self,c,p,v,ch): return self.channels.get((p,v,ch))
    def set_channel_pointer(self,c,p): self.channels[(p.property_id,p.report_variant,p.channel)]=(p.report_id,p.render_id,p.pointer_version)
    def clear_channel_pointer(self,c,p,v,ch): self.channels.pop((p,v,ch),None)
    def list_channel_pointers_for_report(self,c,p,v,r):
        return tuple((ch,val[1]) for (pp,vv,ch),val in self.channels.items() if pp==p and vv==v and val[0]==r)
    def append_history(self,c,r): self.history.append(r)
    def was_previously_published(self,c,p,v,ch,r,rr): return (p,v,ch,r,rr) in self.published

class Guard:
    def evaluate(self,**kw): return NS(allowed=True,reasons=())
class Fresh:
    def check(self,cursor,report): return NS(status='FRESH',reason_code=None)
class Cache:
    def __init__(self): self.events=[]
    def emit(self,cursor,**kw): self.events.append(kw)

def fixtures():
    p,r,r2,rd,rd2=uuid4(),uuid4(),uuid4(),uuid4(),uuid4()
    report=NS(property_id=p,report_variant='PUBLIC',report_id=r)
    render=NS(render_id=rd,report_id=r)
    stage=NS(property_id=p,report_variant='PUBLIC',channel='WEB',report_id=r,render_id=rd,correlation_id=uuid4())
    return p,r,r2,rd,rd2,report,render,stage

def svc(repo,cache=None): return ControlledPublicationLifecycle(repository=repo,guard_engine=Guard(),freshness_checker=Fresh(),cache_events=cache,history_service=PublicationHistoryService(repo))

def test_presentation_only_promotion_changes_channel_not_semantic_current():
    p,r,_,old,new,report,_,stage=fixtures(); repo=Repo(); cache=Cache()
    repo.current[(p,'PUBLIC')]=(r,4); repo.channels[(p,'PUBLIC','WEB')]=(r,old,2)
    render=NS(render_id=new,report_id=r); stage=NS(**{**stage.__dict__,'render_id':new})
    out=svc(repo,cache).promote_render(None,stage=stage,report=report,render=render)
    assert out.status=='PROMOTED'
    assert repo.current[(p,'PUBLIC')]==(r,4)
    assert repo.channels[(p,'PUBLIC','WEB')][1]==new
    assert [x.action for x in repo.history]==['SUPERSEDED','RENDER_PROMOTED']
    assert cache.events[-1]['reason_code']=='RENDER_PROMOTED'

def test_unpublish_removes_only_requested_channel_and_is_idempotent():
    p,r,_,rd,_,_,_,_=fixtures(); repo=Repo(); repo.current[(p,'PUBLIC')]=(r,1); repo.channels[(p,'PUBLIC','WEB')]=(r,rd,1)
    s=svc(repo)
    assert s.unpublish(None,property_id=p,report_variant='PUBLIC',channel='WEB').status=='UNPUBLISHED'
    assert s.unpublish(None,property_id=p,report_variant='PUBLIC',channel='WEB').status=='NO_OP'
    assert repo.current[(p,'PUBLIC')][0]==r

def test_rollback_requires_historical_publication_and_repoints_atomically():
    p,r,_,rd,_,report,render,stage=fixtures(); repo=Repo(); repo.published.add((p,'PUBLIC','WEB',r,rd))
    out=svc(repo).rollback(None,stage=stage,report=report,render=render)
    assert out.status=='ROLLED_BACK' and repo.current[(p,'PUBLIC')][0]==r and repo.channels[(p,'PUBLIC','WEB')][1]==rd
    bad=Repo(); assert svc(bad).rollback(None,stage=stage,report=report,render=render).reason_code=='ROLLBACK_TARGET_NOT_IN_PUBLICATION_HISTORY'

def test_invalidation_clears_only_pointers_that_reference_invalidated_report():
    p,r,r2,rd,rd2,_,_,_=fixtures(); repo=Repo(); repo.current[(p,'PUBLIC')]=(r,1)
    repo.channels[(p,'PUBLIC','WEB')]=(r,rd,1); repo.channels[(p,'PUBLIC','PDF_DOWNLOAD')]=(r2,rd2,1)
    out=svc(repo).invalidate(None,property_id=p,report_variant='PUBLIC',report_id=r)
    assert out.status=='INVALIDATED'; assert (p,'PUBLIC') not in repo.current
    assert (p,'PUBLIC','WEB') not in repo.channels and (p,'PUBLIC','PDF_DOWNLOAD') in repo.channels

def test_withdrawal_removes_semantic_and_all_channels_for_current_report():
    p,r,_,rd,rd2,_,_,_=fixtures(); repo=Repo(); repo.current[(p,'PUBLIC')]=(r,1)
    repo.channels[(p,'PUBLIC','WEB')]=(r,rd,1); repo.channels[(p,'PUBLIC','PRINT')]=(r,rd2,1)
    out=svc(repo).withdraw(None,property_id=p,report_variant='PUBLIC')
    assert out.status=='WITHDRAWN'; assert not repo.current; assert not repo.channels
    assert repo.history[-1].action=='SEMANTIC_WITHDRAWN'
