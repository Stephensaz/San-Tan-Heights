-- STH M2-002: immutable intelligence snapshot persistence.
BEGIN;
CREATE TABLE IF NOT EXISTS snapshot.intelligence_snapshots (
    snapshot_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    property_id uuid NOT NULL REFERENCES core.properties(property_id),
    snapshot_sequence bigint NOT NULL CHECK (snapshot_sequence > 0),
    snapshot_reason text NOT NULL,
    governed_state_version text NOT NULL,
    source_read_token text NOT NULL,
    intelligence_schema_version text NOT NULL,
    governance_schema_version text NOT NULL,
    model_version text NOT NULL,
    semantic_fingerprint char(64) NOT NULL CHECK (semantic_fingerprint ~ '^[0-9a-f]{64}$'),
    agent_semantic_fingerprint char(64) NOT NULL CHECK (agent_semantic_fingerprint ~ '^[0-9a-f]{64}$'),
    seller_semantic_fingerprint char(64) NOT NULL CHECK (seller_semantic_fingerprint ~ '^[0-9a-f]{64}$'),
    public_semantic_fingerprint char(64) NOT NULL CHECK (public_semantic_fingerprint ~ '^[0-9a-f]{64}$'),
    snapshot_hash char(64) NOT NULL CHECK (snapshot_hash ~ '^[0-9a-f]{64}$'),
    snapshot_completeness_status text NOT NULL CHECK (snapshot_completeness_status IN ('COMPLETE','PARTIAL_VALID','BLOCKED','INVALID')),
    qa_status text NOT NULL REFERENCES reference.qa_status(code),
    qa_completed_at timestamptz NULL,
    supersedes_snapshot_id uuid NULL REFERENCES snapshot.intelligence_snapshots(snapshot_id),
    created_at timestamptz NOT NULL DEFAULT now(),
    created_by text NOT NULL,
    UNIQUE(property_id, snapshot_sequence),
    UNIQUE(property_id, semantic_fingerprint)
);

CREATE TABLE IF NOT EXISTS snapshot.snapshot_findings (
    snapshot_finding_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    snapshot_id uuid NOT NULL REFERENCES snapshot.intelligence_snapshots(snapshot_id),
    finding_id text NOT NULL,
    finding_type text NOT NULL,
    passport_id text NOT NULL,
    passport_version text NOT NULL,
    passport_semantic_fingerprint char(64) NOT NULL CHECK (passport_semantic_fingerprint ~ '^[0-9a-f]{64}$'),
    canonical_value jsonb NULL,
    confidence_code text NOT NULL,
    qa_status text NOT NULL REFERENCES reference.qa_status(code),
    production_status text NOT NULL CHECK (production_status IN ('PRODUCTION_READY','INTERNAL_ONLY','BLOCKED','DEPRECATED','SUPERSEDED')),
    publication_scope text NOT NULL CHECK (publication_scope IN ('AGENT','SELLER','PUBLIC','AGENT_SELLER','ALL','NONE')),
    agent_wording text NULL,
    seller_wording text NULL,
    public_wording text NULL,
    agent_wording_version text NULL,
    seller_wording_version text NULL,
    public_wording_version text NULL,
    semantic_fingerprint char(64) NOT NULL CHECK (semantic_fingerprint ~ '^[0-9a-f]{64}$'),
    evidence_reference_set_hash char(64) NOT NULL CHECK (evidence_reference_set_hash ~ '^[0-9a-f]{64}$'),
    UNIQUE(snapshot_id, finding_id)
);

CREATE TABLE IF NOT EXISTS snapshot.snapshot_dependencies (
    snapshot_dependency_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    snapshot_id uuid NOT NULL REFERENCES snapshot.intelligence_snapshots(snapshot_id),
    dependency_type text NOT NULL,
    dependency_id text NOT NULL,
    record_fingerprint char(64) NOT NULL CHECK (record_fingerprint ~ '^[0-9a-f]{64}$'),
    semantic_fingerprint char(64) NOT NULL CHECK (semantic_fingerprint ~ '^[0-9a-f]{64}$'),
    dependency_version text NOT NULL,
    required boolean NOT NULL,
    affects_agent boolean NOT NULL,
    affects_seller boolean NOT NULL,
    affects_public boolean NOT NULL,
    UNIQUE(snapshot_id, dependency_type, dependency_id)
);
COMMIT;
