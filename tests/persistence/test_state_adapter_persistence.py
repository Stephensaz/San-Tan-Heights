from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]

def test_kernel_test_entity_migration_has_version_and_fk():
    sql=(ROOT/'database/migrations/0103_kernel_test_entities.sql').read_text()
    assert 'state_version bigint NOT NULL DEFAULT 1' in sql
    assert 'REFERENCES reference.content_state(code)' in sql

def test_adapter_uses_for_update_and_compare_and_swap():
    text=(ROOT/'src/kernel/state/kernel_test_adapter.py').read_text()
    assert 'FOR UPDATE' in text
    assert 'state_version=%s' in text
    assert 'state_version=state_version+1' in text
