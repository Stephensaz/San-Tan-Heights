-- STH M4-001: render persistence foundation downstream of immutable semantic reports.
BEGIN;

CREATE TABLE IF NOT EXISTS reporting.render_versions (
    render_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    report_id uuid NOT NULL REFERENCES reporting.report_versions(report_id),
    render_type text NOT NULL REFERENCES reference.render_type(code),
    render_version bigint NOT NULL CHECK (render_version > 0),
    render_contract_version text NOT NULL,
    template_id text NOT NULL,
    template_version text NOT NULL,
    renderer_version text NOT NULL,
    presentation_input_hash char(64) NOT NULL CHECK (presentation_input_hash ~ '^[0-9a-f]{64}$'),
    artifact_hash char(64) NULL CHECK (artifact_hash IS NULL OR artifact_hash ~ '^[0-9a-f]{64}$'),
    artifact_size_bytes bigint NULL CHECK (artifact_size_bytes IS NULL OR artifact_size_bytes >= 0),
    storage_uri text NULL,
    mime_type text NULL,
    content_state text NOT NULL REFERENCES reference.content_state(code) DEFAULT 'BUILDING',
    health_state text NOT NULL REFERENCES reference.health_state(code) DEFAULT 'CLEAN',
    qa_status text NOT NULL REFERENCES reference.qa_status(code) DEFAULT 'PENDING',
    qa_completed_at timestamptz NULL,
    publication_eligible boolean NOT NULL DEFAULT false,
    supersedes_render_id uuid NULL REFERENCES reporting.render_versions(render_id),
    superseded_by_render_id uuid NULL REFERENCES reporting.render_versions(render_id),
    created_at timestamptz NOT NULL DEFAULT now(),
    created_by text NOT NULL,
    UNIQUE(report_id, render_type, render_version),
    UNIQUE(report_id, render_type, presentation_input_hash)
);

CREATE TABLE IF NOT EXISTS reporting.render_dependencies (
    render_dependency_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    render_id uuid NOT NULL REFERENCES reporting.render_versions(render_id),
    dependency_type text NOT NULL,
    dependency_id text NOT NULL,
    semantic_fingerprint char(64) NOT NULL CHECK (semantic_fingerprint ~ '^[0-9a-f]{64}$'),
    dependency_version text NOT NULL,
    slot_id text NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE(render_id, dependency_type, dependency_id, slot_id)
);

COMMIT;
