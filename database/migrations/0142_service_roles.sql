-- M6-003: dedicated runtime service roles. Credentials/login roles are provisioned externally.
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='sth_snapshot_service') THEN CREATE ROLE sth_snapshot_service NOLOGIN; END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='sth_report_builder') THEN CREATE ROLE sth_report_builder NOLOGIN; END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='sth_renderer') THEN CREATE ROLE sth_renderer NOLOGIN; END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='sth_publication_service') THEN CREATE ROLE sth_publication_service NOLOGIN; END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='sth_regeneration_worker') THEN CREATE ROLE sth_regeneration_worker NOLOGIN; END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='sth_release_service') THEN CREATE ROLE sth_release_service NOLOGIN; END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='sth_operations_service') THEN CREATE ROLE sth_operations_service NOLOGIN; END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='sth_public_delivery') THEN CREATE ROLE sth_public_delivery NOLOGIN; END IF;
END $$;
