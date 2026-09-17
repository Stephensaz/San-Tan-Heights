BEGIN;
CREATE TABLE IF NOT EXISTS snapshot.snapshot_requirement_results (
    snapshot_requirement_result_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    snapshot_id uuid NOT NULL REFERENCES snapshot.intelligence_snapshots(snapshot_id),
    requirement_id text NOT NULL,
    requirement_scope text NOT NULL,
    required_flag boolean NOT NULL,
    status text NOT NULL CHECK (status IN ('SATISFIED','OPTIONAL_MISSING','BLOCKED','NOT_APPLICABLE')),
    finding_id text NULL,
    dependency_type text NULL,
    dependency_id text NULL,
    reason_code text NULL REFERENCES reference.reason_code(code),
    UNIQUE(snapshot_id, requirement_id)
);
COMMIT;
