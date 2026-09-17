from types import SimpleNamespace as NS
from uuid import uuid4
from src.publication.service import AtomicPublicationService
from src.publication.guards import PublicationGuardEngine
from src.publication.staging import PublicationStagingRepository
from src.publication.repository import PublicationRepository

class Cursor:
    def __init__(self,rows=None): self.rows=list(rows or []); self.calls=[]
    def execute(self,sql,params=None): self.calls.append((sql,params))
    def fetchone(self): return self.rows.pop(0) if self.rows else None
class Fresh:
    def __init__(self,status='FRESH',reason=None): self.status=status; self.reason=reason
    def check(self,cursor,report): return NS(status=self.status,reason_code=self.reason)

def valid():
    prop,rep,rend,st=uuid4(),uuid4(),uuid4(),uuid4()
    stage=NS(staging_id=st,property_id=prop,report_variant='PUBLIC',channel='WEB',report_id=rep,render_id=rend,staging_state='STAGED',correlation_id=uuid4())
    report=NS(property_id=prop,report_variant='PUBLIC',report_id=rep,snapshot_id=uuid4(),content_state='READY',qa_status='PASS',publication_eligible=True,health_state='CLEAN')
    render=NS(render_id=rend,report_id=rep,render_type='WEB',content_state='READY',qa_status='PASS',publication_eligible=True,health_state='CLEAN',storage_uri='s3://x',artifact_hash='a'*64)
    return stage,report,render

def service(fresh='FRESH',reason=None):
    return AtomicPublicationService(staging_repository=PublicationStagingRepository(),publication_repository=PublicationRepository(),guard_engine=PublicationGuardEngine(),freshness_checker=Fresh(fresh,reason))

def test_publish_swaps_both_pointers_and_history_in_one_call_path():
    stage,report,render=valid(); c=Cursor([(stage.staging_id,)])
    out=service().publish(c,stage=stage,report=report,render=render)
    sql='\n'.join(x[0] for x in c.calls)
    assert out.status=='PUBLISHED'
    assert 'pg_advisory_xact_lock' in sql
    assert 'publication.report_current' in sql
    assert 'publication.channel_pointers' in sql
    assert 'publication.publication_history' in sql
    assert sql.index('pg_advisory_xact_lock') < sql.index('publication.report_current')

def test_stale_replacement_never_touches_current_pointers():
    stage,report,render=valid(); c=Cursor([(stage.staging_id,)])
    out=service('STALE','VARIANT_SEMANTIC_FINGERPRINT_CHANGED').publish(c,stage=stage,report=report,render=render)
    sql='\n'.join(x[0] for x in c.calls)
    assert out.status=='STALE'
    assert 'publication.report_current' not in sql and 'publication.channel_pointers' not in sql

def test_guard_failure_never_touches_current_pointers():
    stage,report,render=valid(); render=NS(**{**render.__dict__,'qa_status':'FAIL'}); c=Cursor([(stage.staging_id,)])
    out=service().publish(c,stage=stage,report=report,render=render)
    sql='\n'.join(x[0] for x in c.calls)
    assert out.status=='BLOCKED'
    assert 'publication.report_current' not in sql and 'publication.channel_pointers' not in sql

class Freeze:
    def active(self,cursor,p,v,ch): return (uuid4(),'PUBLICATION_FROZEN')

def test_freeze_blocks_atomic_publish_before_pointer_writes():
    stage,report,render=valid(); c=Cursor([(stage.staging_id,)])
    s=AtomicPublicationService(staging_repository=PublicationStagingRepository(),publication_repository=PublicationRepository(),guard_engine=PublicationGuardEngine(),freshness_checker=Fresh(),freeze_repository=Freeze())
    out=s.publish(c,stage=stage,report=report,render=render)
    sql='\n'.join(x[0] for x in c.calls)
    assert out.status=='BLOCKED' and 'publication.report_current' not in sql and 'publication.channel_pointers' not in sql
