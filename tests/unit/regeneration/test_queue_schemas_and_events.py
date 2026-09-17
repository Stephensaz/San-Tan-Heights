import json,yaml
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
def test_queue_command_and_response_schemas_exist():
    for p in ['schemas/commands/queue-regeneration.schema.json','schemas/responses/queue-regeneration-result.schema.json','schemas/regeneration/retry-policy.schema.json']:
        json.loads((ROOT/p).read_text())
def test_regeneration_queued_event_registered_to_regeneration_service():
    r=yaml.safe_load((ROOT/'registries/events/events.yaml').read_text()); e=next(x for x in r['events'] if x['id']=='REGENERATION_JOB_QUEUED')
    assert 'REGENERATION_SERVICE' in e['producers']
def test_retry_ready_index_is_additive_migration():
    sql=(ROOT/'database/migrations/0063_regeneration_retry_claim_indexes.sql').read_text()
    assert 'regeneration_jobs_retry_ready_idx' in sql and "WHERE job_state='RETRY_WAIT'" in sql
