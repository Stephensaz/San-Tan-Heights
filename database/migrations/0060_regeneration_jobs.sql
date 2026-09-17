-- STH M3-001: regeneration job persistence.
BEGIN;

CREATE TABLE IF NOT EXISTS orchestration.regeneration_jobs (
    job_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    property_id uuid NOT NULL REFERENCES core.properties(property_id),
    report_variant text NOT NULL REFERENCES reference.report_variant(code),
    trigger_event_id uuid NULL REFERENCES audit.orchestration_events(event_id),
    trigger_type text NOT NULL,
    target_snapshot_id uuid NOT NULL REFERENCES snapshot.intelligence_snapshots(snapshot_id),
    old_report_id uuid NULL,
    priority_class text NOT NULL CHECK (priority_class IN ('CRITICAL','HIGH','NORMAL','BULK','LOW')),
    priority_score integer NOT NULL,
    job_target_key text NOT NULL CHECK (job_target_key ~ '^[0-9a-f]{64}$'),
    job_state text NOT NULL REFERENCES reference.job_state(code),
    attempt_count integer NOT NULL DEFAULT 0 CHECK (attempt_count >= 0),
    max_attempts integer NOT NULL DEFAULT 3 CHECK (max_attempts >= 1),
    worker_id text NULL,
    claimed_at timestamptz NULL,
    last_heartbeat_at timestamptz NULL,
    lease_expires_at timestamptz NULL,
    queued_at timestamptz NOT NULL DEFAULT now(),
    started_at timestamptz NULL,
    completed_at timestamptz NULL,
    next_retry_at timestamptz NULL,
    input_hash text NULL CHECK (input_hash IS NULL OR input_hash ~ '^[0-9a-f]{64}$'),
    completion_report_id uuid NULL,
    failure_stage text NULL,
    failure_code text NULL,
    failure_message_safe text NULL,
    stale_reason_code text NULL REFERENCES reference.reason_code(code),
    release_id uuid NULL,
    correlation_id uuid NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

COMMIT;
