from uuid import uuid4
from src.regeneration.repository import RegenerationJob, RegenerationJobRepository

class Cursor:
    def __init__(self, rows=None): self.calls=[]; self.rows=list(rows or [])
    def execute(self,sql,params=None): self.calls.append((sql,params))
    def fetchone(self): return self.rows.pop(0) if self.rows else None

def job():
    return RegenerationJob(uuid4(),uuid4(),'PUBLIC','REPORT_MARKED_DIRTY',uuid4(),'NORMAL',50,'a'*64,uuid4())

def test_insert_targets_regeneration_jobs():
    c=Cursor(); RegenerationJobRepository().insert(c,job())
    assert 'INSERT INTO orchestration.regeneration_jobs' in c.calls[0][0]

def test_find_active_uses_property_variant_target_key():
    jid=uuid4(); c=Cursor([(jid,)])
    j=job(); got=RegenerationJobRepository().find_active(c,j.property_id,j.report_variant,j.job_target_key)
    assert got==jid
    assert "job_state IN ('QUEUED','CLAIMED','RUNNING','RETRY_WAIT')" in c.calls[0][0]

def test_insert_rejects_running_new_job():
    from dataclasses import replace
    import pytest
    with pytest.raises(ValueError): RegenerationJobRepository().insert(Cursor(),replace(job(),job_state='RUNNING'))
