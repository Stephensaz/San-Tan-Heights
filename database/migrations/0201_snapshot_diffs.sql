BEGIN;
CREATE TABLE IF NOT EXISTS snapshot.snapshot_diffs (
    snapshot_diff_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    old_snapshot_id uuid NOT NULL REFERENCES snapshot.intelligence_snapshots(snapshot_id),
    new_snapshot_id uuid NOT NULL REFERENCES snapshot.intelligence_snapshots(snapshot_id),
    diff_payload jsonb NOT NULL,
    diff_hash char(64) NOT NULL CHECK (diff_hash ~ '^[0-9a-f]{64}$'),
    created_at timestamptz NOT NULL DEFAULT now(),
    CHECK (old_snapshot_id <> new_snapshot_id),
    UNIQUE(old_snapshot_id, new_snapshot_id)
);
COMMIT;
