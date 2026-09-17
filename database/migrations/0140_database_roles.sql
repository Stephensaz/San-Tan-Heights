-- STH M1-015: Governed runtime database roles.
-- PostgreSQL role creation cannot be expressed with CREATE ROLE IF NOT EXISTS,
-- so use a guarded DO block. Passwords/credentials are provisioned externally.
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='sth_kernel') THEN CREATE ROLE sth_kernel NOLOGIN; END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='sth_audit_service') THEN CREATE ROLE sth_audit_service NOLOGIN; END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='sth_outbox_worker') THEN CREATE ROLE sth_outbox_worker NOLOGIN; END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='sth_ops_reader') THEN CREATE ROLE sth_ops_reader NOLOGIN; END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='sth_migration') THEN CREATE ROLE sth_migration NOLOGIN; END IF;
END $$;
