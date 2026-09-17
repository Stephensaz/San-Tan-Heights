-- STH M3-024: READY reports are immutable semantic evidence.
BEGIN;
CREATE OR REPLACE FUNCTION reporting.protect_ready_report_semantics()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF OLD.content_state = 'READY' AND (
       NEW.property_id IS DISTINCT FROM OLD.property_id OR
       NEW.report_variant IS DISTINCT FROM OLD.report_variant OR
       NEW.version_number IS DISTINCT FROM OLD.version_number OR
       NEW.snapshot_id IS DISTINCT FROM OLD.snapshot_id OR
       NEW.report_schema_version IS DISTINCT FROM OLD.report_schema_version OR
       NEW.content_contract_version IS DISTINCT FROM OLD.content_contract_version OR
       NEW.variant_policy_version IS DISTINCT FROM OLD.variant_policy_version OR
       NEW.builder_version IS DISTINCT FROM OLD.builder_version OR
       NEW.report_input_hash IS DISTINCT FROM OLD.report_input_hash OR
       NEW.canonical_payload_hash IS DISTINCT FROM OLD.canonical_payload_hash OR
       NEW.stored_payload_hash IS DISTINCT FROM OLD.stored_payload_hash OR
       NEW.canonical_payload IS DISTINCT FROM OLD.canonical_payload OR
       NEW.dependency_manifest_hash IS DISTINCT FROM OLD.dependency_manifest_hash OR
       NEW.generation_reason IS DISTINCT FROM OLD.generation_reason
  ) THEN
    RAISE EXCEPTION 'READY_REPORT_SEMANTICS_IMMUTABLE';
  END IF;
  RETURN NEW;
END $$;

DROP TRIGGER IF EXISTS trg_ready_report_semantics_immutable ON reporting.report_versions;
CREATE TRIGGER trg_ready_report_semantics_immutable
BEFORE UPDATE ON reporting.report_versions
FOR EACH ROW EXECUTE FUNCTION reporting.protect_ready_report_semantics();

CREATE OR REPLACE FUNCTION reporting.protect_ready_report_dependencies()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE parent_state text;
BEGIN
  SELECT content_state INTO parent_state
  FROM reporting.report_versions
  WHERE report_id = COALESCE(OLD.report_id, NEW.report_id);
  IF parent_state = 'READY' THEN
    RAISE EXCEPTION 'READY_REPORT_DEPENDENCIES_IMMUTABLE';
  END IF;
  RETURN COALESCE(NEW, OLD);
END $$;

DROP TRIGGER IF EXISTS trg_ready_report_dependency_update ON reporting.report_dependencies;
CREATE TRIGGER trg_ready_report_dependency_update
BEFORE UPDATE OR DELETE ON reporting.report_dependencies
FOR EACH ROW EXECUTE FUNCTION reporting.protect_ready_report_dependencies();
COMMIT;
