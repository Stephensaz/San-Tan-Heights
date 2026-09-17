-- STH M3-008: immutable semantic report persistence foundation.
BEGIN;
CREATE TABLE IF NOT EXISTS reporting.report_versions (
    report_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    property_id uuid NOT NULL REFERENCES core.properties(property_id),
    report_variant text NOT NULL REFERENCES reference.report_variant(code),
    version_number bigint NOT NULL CHECK (version_number > 0),
    snapshot_id uuid NOT NULL REFERENCES snapshot.intelligence_snapshots(snapshot_id),
    report_schema_version text NOT NULL,
    content_contract_version text NOT NULL,
    variant_policy_version text NOT NULL,
    builder_version text NOT NULL,
    report_input_hash char(64) NOT NULL CHECK (report_input_hash ~ '^[0-9a-f]{64}$'),
    canonical_payload_hash char(64) NOT NULL CHECK (canonical_payload_hash ~ '^[0-9a-f]{64}$'),
    stored_payload_hash char(64) NULL CHECK (stored_payload_hash IS NULL OR stored_payload_hash ~ '^[0-9a-f]{64}$'),
    canonical_payload jsonb NOT NULL,
    dependency_manifest_hash char(64) NOT NULL CHECK (dependency_manifest_hash ~ '^[0-9a-f]{64}$'),
    generation_reason text NOT NULL,
    content_state text NOT NULL REFERENCES reference.content_state(code),
    health_state text NOT NULL REFERENCES reference.health_state(code),
    qa_status text NOT NULL REFERENCES reference.qa_status(code),
    qa_completed_at timestamptz NULL,
    publication_eligible boolean NOT NULL DEFAULT false,
    supersedes_report_id uuid NULL REFERENCES reporting.report_versions(report_id),
    superseded_by_report_id uuid NULL REFERENCES reporting.report_versions(report_id),
    created_at timestamptz NOT NULL DEFAULT now(),
    created_by text NOT NULL,
    UNIQUE(property_id, report_variant, version_number),
    UNIQUE(property_id, report_variant, report_input_hash)
);

CREATE TABLE IF NOT EXISTS reporting.report_dependencies (
    report_dependency_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    report_id uuid NOT NULL REFERENCES reporting.report_versions(report_id),
    dependency_type text NOT NULL,
    dependency_id text NOT NULL,
    semantic_fingerprint char(64) NOT NULL CHECK (semantic_fingerprint ~ '^[0-9a-f]{64}$'),
    dependency_version text NOT NULL,
    source_snapshot_id uuid NOT NULL REFERENCES snapshot.intelligence_snapshots(snapshot_id),
    UNIQUE(report_id, dependency_type, dependency_id)
);
COMMIT;
