-- STH M1-009: Consumer-side event idempotency ledger.
BEGIN;

CREATE TABLE IF NOT EXISTS audit.event_consumptions (
    event_consumption_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    consumer_name text NOT NULL,
    event_id uuid NOT NULL REFERENCES audit.orchestration_events(event_id),
    consumed_at timestamptz NOT NULL DEFAULT now(),
    result_hash char(64) NULL CHECK (result_hash IS NULL OR result_hash ~ '^[0-9a-f]{64}$'),
    UNIQUE (consumer_name, event_id)
);

CREATE INDEX IF NOT EXISTS event_consumptions_event_idx
    ON audit.event_consumptions (event_id);

COMMIT;
