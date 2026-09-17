from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]

def text(name): return (ROOT/'database/migrations'/name).read_text()

def test_regeneration_schema_has_active_target_uniqueness_and_fk_state():
    sql=text('0060_regeneration_jobs.sql')+text('0061_job_indexes.sql')
    assert 'REFERENCES reference.job_state(code)' in sql
    assert 'regeneration_jobs_one_active_target_uq' in sql
    assert "WHERE job_state IN ('QUEUED','CLAIMED','RUNNING','RETRY_WAIT')" in sql

def test_claim_index_is_priority_then_queue_time():
    sql=text('0061_job_indexes.sql')
    assert 'priority_score DESC, queued_at ASC, job_id ASC' in sql
