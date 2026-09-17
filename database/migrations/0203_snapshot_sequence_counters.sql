-- STH M2-011: concurrency-safe snapshot sequence allocation.
BEGIN;
CREATE TABLE IF NOT EXISTS snapshot.snapshot_sequence_counters (
    property_id uuid PRIMARY KEY REFERENCES core.properties(property_id),
    next_sequence bigint NOT NULL CHECK (next_sequence > 0),
    updated_at timestamptz NOT NULL DEFAULT now()
);
COMMIT;
