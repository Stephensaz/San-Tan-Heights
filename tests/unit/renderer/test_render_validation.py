from dataclasses import replace
from hashlib import sha256
from pathlib import Path
from uuid import uuid4
from src.renderer.contracts import RenderContractRegistry
from src.renderer.repository import RenderVersion
from src.renderer.validation import RenderValidationEngine

ROOT=Path(__file__).resolve().parents[3]
BYTES=b'<html><body>ok</body></html>'

def valid_render(**overrides):
    values=dict(render_id=uuid4(),report_id=uuid4(),render_type='WEB',render_version=1,
        render_contract_version='1.0.0',template_id='PROPERTY_REPORT',template_version='1.0.0',
        renderer_version='1.0.0',presentation_input_hash='a'*64,artifact_hash=sha256(BYTES).hexdigest(),
        artifact_size_bytes=len(BYTES),storage_uri='artifact://renders/x',mime_type='text/html',
        content_state='READY',health_state='CLEAN',qa_status='PASS',publication_eligible=True)
    values.update(overrides); return RenderVersion(**values)

def engine(): return RenderValidationEngine(RenderContractRegistry.from_repository(ROOT))

def test_valid_render_passes():
    r=engine().validate(render=valid_render(),artifact_bytes=BYTES)
    assert r.valid and r.issues==()

def test_hash_drift_fails_closed():
    r=engine().validate(render=valid_render(),artifact_bytes=b'changed')
    assert not r.valid and any(x.code=='RENDER_ARTIFACT_HASH_MISMATCH' for x in r.issues)

def test_mime_type_must_match_contract():
    r=engine().validate(render=valid_render(mime_type='application/pdf'),artifact_bytes=BYTES)
    assert any(x.code=='RENDER_MIME_TYPE_INVALID' for x in r.issues)

def test_publication_eligibility_requires_ready_clean_pass_and_source_report():
    r=engine().validate(render=valid_render(content_state='BUILDING',qa_status='PENDING',publication_eligible=False),artifact_bytes=BYTES,report_content_state='STALE')
    codes={x.code for x in r.issues}
    assert {'RENDER_NOT_READY','RENDER_QA_NOT_PASS','RENDER_NOT_PUBLICATION_ELIGIBLE','SOURCE_REPORT_NOT_ELIGIBLE'} <= codes
