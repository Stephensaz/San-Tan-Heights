from types import SimpleNamespace
import pytest
from src.renderer.adapters import PdfRenderAdapter, RenderAdapterError

def req(kind='PDF'):
    return SimpleNamespace(render_type=kind,report_id='r1',property_id='11111111-1111-1111-1111-111111111111')

def payload():
    pid='11111111-1111-1111-1111-111111111111'
    return {'metadata':{'property_id':pid},'property_identity':{'property_id':pid,'address':'123 Example Ave','community':'San Tan Heights'},'summary':['Verified property intelligence.'],'sections':[{'section_id':'summary','title':'Summary','order':1,'card_ids':[]}],'cards':[],'findings':[],'glossary':[],'disclaimers':['Informational only.']}

def test_pdf_render_is_valid_deterministic_pdf():
    a=PdfRenderAdapter().render(request=req(),canonical_payload=payload()); b=PdfRenderAdapter().render(request=req(),canonical_payload=payload())
    assert a.artifact_bytes.startswith(b'%PDF-')
    assert a.artifact_bytes==b.artifact_bytes and a.artifact_hash==b.artifact_hash
    assert a.mime_type=='application/pdf' and a.artifact_size_bytes==len(a.artifact_bytes)

def test_pdf_adapter_rejects_non_pdf_request():
    with pytest.raises(RenderAdapterError): PdfRenderAdapter().render(request=req('WEB'),canonical_payload=payload())
