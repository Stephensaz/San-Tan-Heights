BEGIN;
CREATE OR REPLACE FUNCTION snapshot.prevent_snapshot_content_mutation()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'snapshot history is immutable';
END;
$$;
DROP TRIGGER IF EXISTS trg_snapshot_findings_immutable ON snapshot.snapshot_findings;
CREATE TRIGGER trg_snapshot_findings_immutable BEFORE UPDATE OR DELETE ON snapshot.snapshot_findings FOR EACH ROW EXECUTE FUNCTION snapshot.prevent_snapshot_content_mutation();
DROP TRIGGER IF EXISTS trg_snapshot_dependencies_immutable ON snapshot.snapshot_dependencies;
CREATE TRIGGER trg_snapshot_dependencies_immutable BEFORE UPDATE OR DELETE ON snapshot.snapshot_dependencies FOR EACH ROW EXECUTE FUNCTION snapshot.prevent_snapshot_content_mutation();
DROP TRIGGER IF EXISTS trg_snapshot_requirements_immutable ON snapshot.snapshot_requirement_results;
CREATE TRIGGER trg_snapshot_requirements_immutable BEFORE UPDATE OR DELETE ON snapshot.snapshot_requirement_results FOR EACH ROW EXECUTE FUNCTION snapshot.prevent_snapshot_content_mutation();
DROP TRIGGER IF EXISTS trg_snapshot_diffs_immutable ON snapshot.snapshot_diffs;
CREATE TRIGGER trg_snapshot_diffs_immutable BEFORE UPDATE OR DELETE ON snapshot.snapshot_diffs FOR EACH ROW EXECUTE FUNCTION snapshot.prevent_snapshot_content_mutation();
COMMIT;
