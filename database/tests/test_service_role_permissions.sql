-- M6-003 executable PostgreSQL least-privilege assertions. Run after migrations in live certification.
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='sth_publication_service') THEN RAISE EXCEPTION 'sth_publication_service missing'; END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='sth_public_delivery') THEN RAISE EXCEPTION 'sth_public_delivery missing'; END IF;
  IF NOT has_table_privilege('sth_publication_service','publication.report_current','UPDATE') THEN RAISE EXCEPTION 'publication service needs pointer update'; END IF;
  IF has_table_privilege('sth_release_service','publication.report_current','UPDATE') THEN RAISE EXCEPTION 'release service must not directly update publication pointers'; END IF;
  IF has_table_privilege('sth_public_delivery','reporting.report_versions','SELECT') THEN RAISE EXCEPTION 'public delivery must not read historical report base table'; END IF;
  IF NOT has_table_privilege('sth_public_delivery','publication.current_public_reports','SELECT') THEN RAISE EXCEPTION 'public delivery needs current public report projection'; END IF;
  IF has_table_privilege('sth_renderer','publication.channel_pointers','UPDATE') THEN RAISE EXCEPTION 'renderer must not mutate publication'; END IF;
  IF has_table_privilege('sth_snapshot_service','reporting.report_versions','INSERT') THEN RAISE EXCEPTION 'snapshot service must not create reports'; END IF;
END $$;
