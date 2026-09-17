-- STH M7-027 remediation: create snapshot sequence counters before least-privilege grants consume it.
BEGIN;
CREATE TABLE IF NOT EXISTS snapshot.snapshot_sequence_counters (
    property_id uuid PRIMARY KEY REFERENCES core.properties(property_id),
    next_sequence bigint NOT NULL CHECK (next_sequence > 0),
    updated_at timestamptz NOT NULL DEFAULT now()
);
COMMIT;
