from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]

def test_publication_pointer_tables_and_history_exist():
    sql=(ROOT/'database/migrations/0045_publication_persistence.sql').read_text()
    assert 'publication.report_current' in sql
    assert 'publication.channel_pointers' in sql
    assert 'publication.publication_history' in sql
    assert 'PRIMARY KEY(property_id, report_variant)' in sql
    assert 'PRIMARY KEY(property_id, report_variant, channel)' in sql

def test_publication_history_is_append_only():
    sql=(ROOT/'database/migrations/0046_publication_history_immutability.sql').read_text()
    assert 'BEFORE UPDATE OR DELETE ON publication.publication_history' in sql
    assert 'audit.prevent_immutable_mutation()' in sql
