from hashlib import sha256
from uuid import uuid4
from src.renderer.repository import RenderVersion
from src.renderer.storage import StorageIntegrityEngine

DATA=b'abc123'
def render(**kw):
    d=dict(render_id=uuid4(),report_id=uuid4(),render_type='PDF',render_version=1,render_contract_version='1.0.0',template_id='T',template_version='1',renderer_version='1',presentation_input_hash='a'*64,artifact_hash=sha256(DATA).hexdigest(),artifact_size_bytes=len(DATA),storage_uri='artifact://r/1',mime_type='application/pdf')
    d.update(kw); return RenderVersion(**d)

def test_storage_bytes_match_db_evidence():
    assert StorageIntegrityEngine().verify(render=render(),stored_bytes=DATA).valid

def test_storage_hash_or_size_drift_fails():
    e=StorageIntegrityEngine()
    assert e.verify(render=render(),stored_bytes=b'other').code in {'STORAGE_SIZE_MISMATCH','STORAGE_HASH_MISMATCH'}

def test_missing_storage_evidence_fails_closed():
    assert StorageIntegrityEngine().verify(render=render(storage_uri=None),stored_bytes=DATA).code=='RENDER_STORAGE_URI_MISSING'
