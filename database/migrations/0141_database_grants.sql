-- STH M1-015: Least-privilege grants for the governed lifecycle kernel.
BEGIN;

REVOKE ALL ON SCHEMA audit, operations, reference FROM PUBLIC;
REVOKE ALL ON ALL TABLES IN SCHEMA audit, operations, reference FROM PUBLIC;

GRANT USAGE ON SCHEMA audit, operations, reference TO sth_kernel;
GRANT SELECT ON ALL TABLES IN SCHEMA reference TO sth_kernel;
GRANT SELECT, INSERT, UPDATE ON operations.kernel_test_entities TO sth_kernel;
GRANT SELECT, INSERT ON audit.processed_commands TO sth_kernel;
GRANT INSERT ON audit.orchestration_events, audit.state_transitions, audit.guard_evaluations, audit.event_outbox TO sth_kernel;
GRANT SELECT ON audit.orchestration_events TO sth_kernel;

GRANT USAGE ON SCHEMA audit, reference TO sth_audit_service;
GRANT SELECT ON ALL TABLES IN SCHEMA reference TO sth_audit_service;
GRANT INSERT ON audit.orchestration_events, audit.state_transitions, audit.guard_evaluations TO sth_audit_service;

GRANT USAGE ON SCHEMA audit TO sth_outbox_worker;
GRANT SELECT ON audit.orchestration_events TO sth_outbox_worker;
GRANT SELECT, UPDATE ON audit.event_outbox TO sth_outbox_worker;
GRANT SELECT, INSERT ON audit.event_consumptions TO sth_outbox_worker;

GRANT USAGE ON SCHEMA audit, operations, reference TO sth_ops_reader;
GRANT SELECT ON ALL TABLES IN SCHEMA audit, operations, reference TO sth_ops_reader;

-- Migration role is intentionally separate from runtime roles. Actual ownership
-- transfer is environment-specific; this grants the capabilities needed by the migration runner.
GRANT USAGE, CREATE ON SCHEMA core, snapshot, reporting, publication, orchestration, audit, operations, security, reference TO sth_migration;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA core, snapshot, reporting, publication, orchestration, audit, operations, security, reference TO sth_migration;

COMMIT;
