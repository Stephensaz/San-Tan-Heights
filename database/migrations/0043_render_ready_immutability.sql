-- STH M4-013: READY render artifact and presentation evidence are immutable.
BEGIN;
CREATE OR REPLACE FUNCTION reporting.protect_ready_render_artifact()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF OLD.content_state = 'READY' AND (
       NEW.report_id IS DISTINCT FROM OLD.report_id OR
       NEW.render_type IS DISTINCT FROM OLD.render_type OR
       NEW.render_version IS DISTINCT FROM OLD.render_version OR
       NEW.render_contract_version IS DISTINCT FROM OLD.render_contract_version OR
       NEW.template_id IS DISTINCT FROM OLD.template_id OR
       NEW.template_version IS DISTINCT FROM OLD.template_version OR
       NEW.renderer_version IS DISTINCT FROM OLD.renderer_version OR
       NEW.presentation_input_hash IS DISTINCT FROM OLD.presentation_input_hash OR
       NEW.artifact_hash IS DISTINCT FROM OLD.artifact_hash OR
       NEW.artifact_size_bytes IS DISTINCT FROM OLD.artifact_size_bytes OR
       NEW.storage_uri IS DISTINCT FROM OLD.storage_uri OR
       NEW.mime_type IS DISTINCT FROM OLD.mime_type
  ) THEN
    RAISE EXCEPTION 'READY_RENDER_ARTIFACT_IMMUTABLE';
  END IF;
  RETURN NEW;
END $$;
DROP TRIGGER IF EXISTS trg_ready_render_artifact_immutable ON reporting.render_versions;
CREATE TRIGGER trg_ready_render_artifact_immutable
BEFORE UPDATE ON reporting.render_versions
FOR EACH ROW EXECUTE FUNCTION reporting.protect_ready_render_artifact();

CREATE OR REPLACE FUNCTION reporting.protect_ready_render_dependencies()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE parent_state text;
BEGIN
  SELECT content_state INTO parent_state FROM reporting.render_versions
  WHERE render_id = COALESCE(OLD.render_id, NEW.render_id);
  IF parent_state = 'READY' THEN
    RAISE EXCEPTION 'READY_RENDER_DEPENDENCIES_IMMUTABLE';
  END IF;
  RETURN COALESCE(NEW, OLD);
END $$;
DROP TRIGGER IF EXISTS trg_ready_render_dependency_update ON reporting.render_dependencies;
CREATE TRIGGER trg_ready_render_dependency_update
BEFORE UPDATE OR DELETE ON reporting.render_dependencies
FOR EACH ROW EXECUTE FUNCTION reporting.protect_ready_render_dependencies();
COMMIT;
