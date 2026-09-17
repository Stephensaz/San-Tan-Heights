from types import SimpleNamespace
import pytest
from src.renderer.adapters import PrintRenderAdapter, PdfRenderAdapter, RenderAdapterError

def req(kind): return SimpleNamespace(render_type=kind,report_id='r1',property_id='11111111-1111-1111-1111-111111111111')
def payload():
    pid='11111111-1111-1111-1111-111111111111'
    return {'metadata':{'property_id':pid},'property_identity':{'property_id':pid,'address':'123 Example Ave','community':'San Tan Heights'},'summary':['Same governed meaning.'],'sections':[],'cards':[],'findings':[],'glossary':[],'disclaimers':['Informational only.']}

def test_print_render_is_deterministic_pdf_and_distinct_from_pdf_presentation():
    a=PrintRenderAdapter().render(request=req('PRINT'),canonical_payload=payload()); b=PrintRenderAdapter().render(request=req('PRINT'),canonical_payload=payload())
    pdf=PdfRenderAdapter().render(request=req('PDF'),canonical_payload=payload())
    assert a.artifact_bytes.startswith(b'%PDF-') and a.artifact_bytes==b.artifact_bytes
    assert a.artifact_hash != pdf.artifact_hash

def test_print_adapter_rejects_wrong_type():
    with pytest.raises(RenderAdapterError): PrintRenderAdapter().render(request=req('PDF'),canonical_payload=payload())
