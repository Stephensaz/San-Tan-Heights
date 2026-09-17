from uuid import uuid4
from src.publication.staging import PublicationStage, PublicationStagingRepository

class Cursor:
    def __init__(self,rows=None): self.rows=list(rows or []); self.calls=[]
    def execute(self,sql,params=None): self.calls.append((sql,params))
    def fetchone(self): return self.rows.pop(0) if self.rows else None

def test_stage_insert_is_idempotent_by_exact_target():
    c=Cursor(); s=PublicationStage(uuid4(),uuid4(),'PUBLIC','WEB',uuid4(),uuid4(),requested_by='test')
    PublicationStagingRepository().insert(c,s)
    assert 'ON CONFLICT (property_id,report_variant,channel,report_id,render_id) DO NOTHING' in c.calls[0][0]

def test_stage_transition_is_compare_and_set():
    c=Cursor([(uuid4(),)])
    assert PublicationStagingRepository().transition(c,uuid4(),from_state='STAGED',to_state='READY')
    assert 'staging_state=%s' in c.calls[0][0] and 'AND staging_state=%s' in c.calls[0][0]
