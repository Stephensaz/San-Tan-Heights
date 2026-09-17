CREATE TABLE IF NOT EXISTS operations.review_items (
    review_item_id uuid PRIMARY KEY,
    review_type text NOT NULL,
    status text NOT NULL CHECK (status IN ('OPEN','RESOLVED','CANCELLED')),
    property_id uuid REFERENCES core.properties(property_id) ON DELETE RESTRICT,
    report_id uuid,
    source_event_id uuid,
    reason_code text NOT NULL,
    safe_context jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    resolved_at timestamptz,
    correlation_id uuid NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_review_items_open ON operations.review_items(status, review_type, created_at);
