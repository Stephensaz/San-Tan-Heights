from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]

def test_audit_tables_defined_with_core_lineage_fields():
    text=(ROOT/'database/migrations/0070_audit_tables.sql').read_text().lower()
    for table in ['audit.orchestration_events','audit.state_transitions','audit.guard_evaluations']:
        assert f'create table if not exists {table}' in text
    for field in ['correlation_id','payload_hash','causation_event_id','reason_code']:
        assert field in text

def test_audit_immutability_triggers_cover_all_tables():
    text=(ROOT/'database/migrations/0121_immutability_triggers.sql').read_text().lower()
    for table in ['audit.orchestration_events','audit.state_transitions','audit.guard_evaluations']:
        assert f'on {table}' in text
    assert text.count('before update or delete') == 3

def test_audit_indexes_exist():
    text=(ROOT/'database/migrations/0071_audit_indexes.sql').read_text().lower()
    assert 'idx_orch_events_correlation' in text
    assert 'idx_state_transitions_entity' in text
    assert 'idx_guard_evaluations_transition' in text
