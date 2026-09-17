from types import SimpleNamespace
import pytest
from src.renderer.adapters import WebRenderAdapter, RenderAdapterError

def req(kind='WEB'):
    return SimpleNamespace(render_type=kind,report_id='r1',property_id='11111111-1111-1111-1111-111111111111',presentation_input_hash='a'*64,profile=SimpleNamespace(template_id='PROPERTY_REPORT'))

def payload():
    pid='11111111-1111-1111-1111-111111111111'
    return {'metadata':{'property_id':pid},'property_identity':{'property_id':pid,'address':'123 <Example> Ave','community':'San Tan Heights'},'summary':['Verified & governed.'],'sections':[{'section_id':'lot-location','title':'Lot & Location','order':1,'card_ids':['c1']}],'cards':[{'card_id':'c1','title':'Rear Context','body':None,'finding_ids':['f1']}],'findings':[{'finding_id':'f1','label':'Rear Property Relationship','display_text':'Recorded common area','limitation':'Does not guarantee a view.'}],'glossary':[{'label':'Verified','definition':'Supported by governed evidence.'}],'disclaimers':['Informational only.']}

def test_web_render_is_deterministic_and_escaped():
    a=WebRenderAdapter().render(request=req(),canonical_payload=payload()); b=WebRenderAdapter().render(request=req(),canonical_payload=payload())
    assert a.artifact_bytes==b.artifact_bytes and a.artifact_hash==b.artifact_hash
    text=a.artifact_bytes.decode(); assert '123 &lt;Example&gt; Ave' in text and 'Verified &amp; governed.' in text
    assert a.mime_type=='text/html'

def test_web_adapter_rejects_wrong_render_type_or_property():
    with pytest.raises(RenderAdapterError): WebRenderAdapter().render(request=req('PDF'),canonical_payload=payload())
    bad=payload(); bad['metadata']['property_id']='22222222-2222-2222-2222-222222222222'
    with pytest.raises(RenderAdapterError): WebRenderAdapter().render(request=req(),canonical_payload=bad)
