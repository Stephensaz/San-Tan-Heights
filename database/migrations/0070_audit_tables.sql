-- STH M1-007: Immutable audit/event persistence.
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

CREATE TABLE IF NOT EXISTS audit.state_transitions (
    transition_record_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    transition_id text NOT NULL,
    entity_type text NOT NULL,
    entity_id uuid NOT NULL,
    state_dimension text NOT NULL,
    from_state text NOT NULL,
    to_state text NOT NULL,
    result text NOT NULL CHECK (result IN ('APPLIED','REJECTED','BLOCKED','NO_OP','CONFLICT','FAILED')),
    reason_code text NULL REFERENCES reference.reason_code(code),
    event_id uuid NULL REFERENCES audit.orchestration_events(event_id),
    correlation_id uuid NOT NULL,
    actor_type text NOT NULL,
    actor_id text NOT NULL,
    recorded_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS audit.guard_evaluations (
    guard_evaluation_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    transition_record_id uuid NULL REFERENCES audit.state_transitions(transition_record_id),
    guard_id text NOT NULL REFERENCES reference.guard_id(code),
    ordinal integer NOT NULL CHECK (ordinal >= 0),
    result text NOT NULL CHECK (result IN ('PASS','FAIL','BLOCK','ERROR','NOT_EVALUATED')),
    reason_code text NULL REFERENCES reference.reason_code(code),
    safe_details jsonb NOT NULL DEFAULT '{}'::jsonb,
    correlation_id uuid NOT NULL,
    evaluated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (transition_record_id, guard_id, ordinal)
);

COMMIT;
