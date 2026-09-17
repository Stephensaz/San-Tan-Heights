-- STH M4-012/M4-014: accepted render completeness and storage evidence constraints.
BEGIN;
ALTER TABLE reporting.render_versions
  DROP CONSTRAINT IF EXISTS ck_ready_render_artifact_complete;
ALTER TABLE reporting.render_versions
  ADD CONSTRAINT ck_ready_render_artifact_complete CHECK (
    content_state <> 'READY' OR (
      artifact_hash IS NOT NULL AND artifact_size_bytes IS NOT NULL AND storage_uri IS NOT NULL AND mime_type IS NOT NULL
      AND health_state = 'CLEAN' AND qa_status = 'PASS' AND publication_eligible = true
    )
  );
COMMIT;
