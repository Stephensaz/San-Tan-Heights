-- STH M3-008: report lookup and reverse-dependency indexes.
BEGIN;
CREATE INDEX IF NOT EXISTS idx_report_versions_property_variant_created
ON reporting.report_versions(property_id, report_variant, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_report_versions_snapshot
ON reporting.report_versions(snapshot_id);
CREATE INDEX IF NOT EXISTS idx_report_dependencies_reverse
ON reporting.report_dependencies(dependency_type, dependency_id, report_id);
COMMIT;
