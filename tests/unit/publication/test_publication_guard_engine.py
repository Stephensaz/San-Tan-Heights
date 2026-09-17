from types import SimpleNamespace as NS
from uuid import uuid4
from src.publication.guards import PublicationGuardEngine

def valid():
    prop,rep,rend=uuid4(),uuid4(),uuid4()
    stage=NS(property_id=prop,report_variant='PUBLIC',channel='WEB',report_id=rep,render_id=rend,staging_state='STAGED')
    report=NS(property_id=prop,report_variant='PUBLIC',report_id=rep,content_state='READY',qa_status='PASS',publication_eligible=True,health_state='CLEAN')
    render=NS(render_id=rend,report_id=rep,render_type='WEB',content_state='READY',qa_status='PASS',publication_eligible=True,health_state='CLEAN',storage_uri='s3://x',artifact_hash='a'*64)
    return stage,report,render

def test_guard_allows_exact_eligible_lineage():
    stage,report,render=valid()
    assert PublicationGuardEngine().evaluate(stage=stage,report=report,render=render).allowed

def test_guard_fails_closed_on_channel_render_mismatch():
    stage,report,render=valid(); render=NS(**{**render.__dict__,'render_type':'PDF'})
    r=PublicationGuardEngine().evaluate(stage=stage,report=report,render=render)
    assert not r.allowed and 'RENDER_CHANNEL_MISMATCH' in r.reasons

def test_guard_fails_closed_if_report_or_render_not_eligible():
    stage,report,render=valid(); report=NS(**{**report.__dict__,'publication_eligible':False})
    assert 'REPORT_NOT_PUBLICATION_ELIGIBLE' in PublicationGuardEngine().evaluate(stage=stage,report=report,render=render).reasons
