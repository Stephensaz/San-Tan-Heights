-- STH M3-022: configuration dependencies are not snapshot-owned.
BEGIN;
ALTER TABLE reporting.report_dependencies
    ALTER COLUMN source_snapshot_id DROP NOT NULL;
COMMIT;
