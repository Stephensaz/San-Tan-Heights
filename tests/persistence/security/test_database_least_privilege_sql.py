from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]

def test_dedicated_service_roles_are_no_login_and_registry_aligned():
    roles=(ROOT/'database/migrations/0142_service_roles.sql').read_text()
    registry=(ROOT/'registries/security/service-identities-v1.0.yaml').read_text()
    for role in ['sth_snapshot_service','sth_report_builder','sth_renderer','sth_publication_service','sth_regeneration_worker','sth_release_service','sth_operations_service','sth_public_delivery']:
        assert f'CREATE ROLE {role} NOLOGIN' in roles
        assert f'database_role: {role}' in registry

def test_public_is_revoked_and_public_delivery_has_no_base_reporting_grant():
    sql=(ROOT/'database/migrations/0143_least_privilege_completion.sql').read_text()
    upper=sql.upper()
    assert 'REVOKE ALL ON SCHEMA CORE, SNAPSHOT, REPORTING, PUBLICATION, ORCHESTRATION, AUDIT, OPERATIONS, SECURITY, REFERENCE FROM PUBLIC' in upper
    assert 'GRANT SELECT ON PUBLICATION.CURRENT_PUBLIC_REPORTS, PUBLICATION.CURRENT_PUBLIC_RENDERS TO STH_PUBLIC_DELIVERY' in upper
    assert 'GRANT SELECT ON REPORTING.REPORT_VERSIONS TO STH_PUBLIC_DELIVERY' not in upper
    assert 'GRANT SELECT ON REPORTING.RENDER_VERSIONS TO STH_PUBLIC_DELIVERY' not in upper

def test_release_role_cannot_directly_mutate_publication_pointers():
    sql=(ROOT/'database/migrations/0143_least_privilege_completion.sql').read_text().upper()
    assert 'GRANT SELECT ON PUBLICATION.REPORT_CURRENT, PUBLICATION.CHANNEL_POINTERS' in sql
    assert 'GRANT SELECT, INSERT, UPDATE, DELETE ON PUBLICATION.REPORT_CURRENT, PUBLICATION.CHANNEL_POINTERS TO STH_RELEASE_SERVICE' not in sql

def test_default_privileges_revoke_public_for_future_objects():
    sql=(ROOT/'database/migrations/0143_least_privilege_completion.sql').read_text().upper()
    assert 'ALTER DEFAULT PRIVILEGES FOR ROLE STH_MIGRATION' in sql
    assert 'REVOKE ALL ON TABLES FROM PUBLIC' in sql
