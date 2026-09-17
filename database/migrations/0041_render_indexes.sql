-- STH M4-001: render lookup and reverse-dependency indexes.
BEGIN;
CREATE INDEX IF NOT EXISTS idx_render_versions_report_type
    ON reporting.render_versions (report_id, render_type, render_version DESC);
CREATE INDEX IF NOT EXISTS idx_render_versions_state
    ON reporting.render_versions (content_state, qa_status, publication_eligible);
CREATE INDEX IF NOT EXISTS idx_render_versions_artifact_hash
    ON reporting.render_versions (artifact_hash) WHERE artifact_hash IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_render_dependencies_reverse
    ON reporting.render_dependencies (dependency_type, dependency_id, semantic_fingerprint);
COMMIT;
