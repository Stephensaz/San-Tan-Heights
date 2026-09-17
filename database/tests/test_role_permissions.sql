-- M1-015 executable PostgreSQL assertions for an integration environment.
-- This file is intended to be run after migrations by a privileged test role.
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='sth_kernel') THEN RAISE EXCEPTION 'sth_kernel missing'; END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='sth_outbox_worker') THEN RAISE EXCEPTION 'sth_outbox_worker missing'; END IF;
  IF has_table_privilege('sth_kernel','audit.orchestration_events','DELETE') THEN RAISE EXCEPTION 'sth_kernel must not DELETE audit events'; END IF;
  IF has_table_privilege('sth_kernel','audit.orchestration_events','UPDATE') THEN RAISE EXCEPTION 'sth_kernel must not UPDATE audit events'; END IF;
  IF NOT has_table_privilege('sth_kernel','audit.orchestration_events','INSERT') THEN RAISE EXCEPTION 'sth_kernel needs INSERT audit events'; END IF;
  IF has_table_privilege('sth_outbox_worker','operations.kernel_test_entities','UPDATE') THEN RAISE EXCEPTION 'outbox worker must not mutate domain state'; END IF;
END $$;
