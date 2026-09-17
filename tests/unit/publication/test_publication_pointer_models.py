from uuid import uuid4
from src.publication.repository import PublicationRepository, CurrentReportPointer, ChannelPointer
from src.publication.current import CurrentSemanticReportModel
from src.publication.channels import PublicationChannelPointerModel

class Cursor:
    def __init__(self, rows=None): self.rows=list(rows or []); self.calls=[]
    def execute(self,sql,params=None): self.calls.append((sql,params))
    def fetchone(self): return self.rows.pop(0) if self.rows else None

def test_current_semantic_report_is_explicit_pointer_not_max_version():
    report_id=uuid4(); c=Cursor([(report_id,7)])
    result=CurrentSemanticReportModel(PublicationRepository()).resolve(c,property_id=uuid4(),report_variant='PUBLIC')
    assert result==(report_id,7)
    assert 'MAX(' not in c.calls[0][0].upper()
    assert 'publication.report_current' in c.calls[0][0]

def test_channel_current_is_explicit_render_pointer():
    report_id,render_id=uuid4(),uuid4(); c=Cursor([(report_id,render_id,4)])
    result=PublicationChannelPointerModel(PublicationRepository()).resolve(c,property_id=uuid4(),report_variant='SELLER',channel='PDF_DOWNLOAD')
    assert result==(report_id,render_id,4)
    assert 'MAX(' not in c.calls[0][0].upper()
    assert 'publication.channel_pointers' in c.calls[0][0]

def test_pointer_updates_are_separate_semantic_and_channel_operations():
    repo=PublicationRepository(); c=Cursor(); prop,rep,rend=uuid4(),uuid4(),uuid4()
    repo.set_current_report(c,CurrentReportPointer(prop,'AGENT',rep))
    repo.set_channel_pointer(c,ChannelPointer(prop,'AGENT','WEB',rep,rend))
    assert 'publication.report_current' in c.calls[0][0]
    assert 'publication.channel_pointers' in c.calls[1][0]

def test_unknown_channel_fails_closed():
    repo=PublicationRepository(); c=Cursor()
    try: repo.get_channel_pointer(c,uuid4(),'PUBLIC','MOBILE_PREVIEW')
    except ValueError: pass
    else: raise AssertionError('expected ValueError')
