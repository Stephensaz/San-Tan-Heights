BEGIN;
CREATE INDEX IF NOT EXISTS idx_snapshots_property_created ON snapshot.intelligence_snapshots(property_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_snapshot_findings_snapshot ON snapshot.snapshot_findings(snapshot_id);
CREATE INDEX IF NOT EXISTS idx_snapshot_dependencies_lookup ON snapshot.snapshot_dependencies(dependency_type, dependency_id);
CREATE INDEX IF NOT EXISTS idx_snapshot_dependencies_snapshot ON snapshot.snapshot_dependencies(snapshot_id);
COMMIT;
