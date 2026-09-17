from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]


def read(name): return (ROOT/'database'/'migrations'/name).read_text()


def test_processed_command_ledger_constraints():
    sql=read('0073_processed_commands.sql')
    assert 'UNIQUE (service_name, idempotency_key)' in sql
    assert 'request_hash char(64)' in sql
    assert 'result_payload jsonb' in sql


def test_outbox_is_transactional_and_leaseable():
    sql=read('0072_outbox.sql')
    assert "'PENDING','CLAIMED','RETRY','DELIVERED','DEAD_LETTER'" in sql
    assert 'UNIQUE (event_id, topic)' in sql
    assert 'lease_expires_at' in sql


def test_event_consumption_has_consumer_event_uniqueness():
    sql=read('0074_event_consumptions.sql')
    assert 'UNIQUE (consumer_name, event_id)' in sql
