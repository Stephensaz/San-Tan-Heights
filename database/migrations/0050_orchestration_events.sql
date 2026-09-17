-- STH M7-027 remediation: establish orchestration event lineage before
-- regeneration-job persistence introduces a foreign-key reference to it.
BEGIN;

CREATE TABLE IF NOT EXISTS audit.orchestration_events (
    event_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    event_type text NOT NULL REFERENCES reference.event_type(code),
    event_version integer NOT NULL CHECK (event_version > 0),
    occurred_at timestamptz NOT NULL,
    recorded_at timestamptz NOT NULL DEFAULT now(),
    property_id uuid NULL,
    report_id uuid NULL,
    snapshot_id uuid NULL,
    job_id uuid NULL,
    release_id uuid NULL,
    correlation_id uuid NOT NULL,
    causation_event_id uuid NULL REFERENCES audit.orchestration_events(event_id),
    actor_type text NOT NULL,
    actor_id text NOT NULL,
    source_system text NOT NULL,
    reason_code text NULL REFERENCES reference.reason_code(code),
    payload jsonb NOT NULL DEFAULT '{}'::jsonb,
    payload_hash char(64) NOT NULL CHECK (payload_hash ~ '^[0-9a-f]{64}$'),
    CONSTRAINT orchestration_events_recorded_after_occurred CHECK (recorded_at >= occurred_at)
);

COMMIT;
