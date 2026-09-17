from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]

def test_database_roles_are_separate_and_no_login():
    sql=(ROOT/'database/migrations/0140_database_roles.sql').read_text()
    for role in ('sth_kernel','sth_audit_service','sth_outbox_worker','sth_ops_reader','sth_migration'):
        assert role in sql
    assert sql.count('NOLOGIN') >= 5


def test_runtime_roles_do_not_receive_audit_delete_or_domain_mutation():
    sql=(ROOT/'database/migrations/0141_database_grants.sql').read_text()
    assert 'INSERT ON audit.orchestration_events' in sql
    assert 'SELECT, UPDATE ON audit.event_outbox TO sth_outbox_worker' in sql
    assert 'operations.kernel_test_entities TO sth_outbox_worker' not in sql
    assert 'DELETE ON audit.orchestration_events' not in sql
    assert 'UPDATE ON audit.orchestration_events' not in sql


def test_executable_role_assertions_exist():
    sql=(ROOT/'database/tests/test_role_permissions.sql').read_text()
    assert "has_table_privilege('sth_kernel','audit.orchestration_events','DELETE')" in sql
    assert "has_table_privilege('sth_outbox_worker','operations.kernel_test_entities','UPDATE')" in sql
