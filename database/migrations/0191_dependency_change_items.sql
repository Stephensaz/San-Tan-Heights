CREATE TABLE IF NOT EXISTS orchestration.dependency_change_items (
    item_id uuid PRIMARY KEY,
    batch_id uuid NOT NULL REFERENCES orchestration.dependency_change_batches(batch_id) ON DELETE RESTRICT,
    property_id uuid NOT NULL REFERENCES core.properties(property_id) ON DELETE RESTRICT,
    dependency_id text NOT NULL,
    old_fingerprint text,
    new_fingerprint text,
    change_class text NOT NULL,
    required_state_blocked boolean NOT NULL DEFAULT false,
    item_state text NOT NULL CHECK (item_state IN ('PENDING','EVALUATING','COMPLETE','FAILED','BLOCKED')),
    result_summary jsonb,
    last_error_code text,
    created_at timestamptz NOT NULL DEFAULT now(),
    evaluated_at timestamptz,
    UNIQUE (batch_id, property_id, dependency_id)
);
CREATE INDEX IF NOT EXISTS idx_dependency_change_items_batch_state ON orchestration.dependency_change_items(batch_id, item_state, property_id, dependency_id);
