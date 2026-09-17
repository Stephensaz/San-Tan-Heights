CREATE TABLE IF NOT EXISTS orchestration.dependency_change_batches (
    batch_id uuid PRIMARY KEY,
    dependency_type text NOT NULL,
    source_change_id text NOT NULL,
    old_version text,
    new_version text,
    batch_state text NOT NULL CHECK (batch_state IN ('DISCOVERING','EVALUATING','COMPLETE','PARTIAL_FAILURE','BLOCKED')),
    candidate_property_count integer NOT NULL DEFAULT 0 CHECK (candidate_property_count >= 0),
    evaluated_property_count integer NOT NULL DEFAULT 0 CHECK (evaluated_property_count >= 0),
    affected_property_count integer NOT NULL DEFAULT 0 CHECK (affected_property_count >= 0),
    created_at timestamptz NOT NULL DEFAULT now(),
    completed_at timestamptz,
    correlation_id uuid NOT NULL,
    UNIQUE (dependency_type, source_change_id)
);
CREATE INDEX IF NOT EXISTS idx_dependency_change_batches_state ON orchestration.dependency_change_batches(batch_state, created_at);
