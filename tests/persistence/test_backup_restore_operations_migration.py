from pathlib import Path
S=(Path(__file__).parents[2]/'database/migrations/0085_backup_restore_operations.sql').read_text()
def test_backup_restore_tables_and_global_freeze_exist():
    assert 'operations.backup_verifications' in S
    assert 'operations.restore_verifications' in S
    assert 'operations.global_publication_freezes' in S
    assert 'uq_global_publication_freeze_active' in S
def test_dashboard_is_view_not_authoritative_table():
    assert 'CREATE OR REPLACE VIEW operations.operations_dashboard_current' in S
