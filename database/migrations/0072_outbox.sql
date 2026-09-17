-- STH M1-009: Transactional event outbox.
BEGIN;

CREATE TABLE IF NOT EXISTS audit.event_outbox (
    outbox_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    event_id uuid NOT NULL REFERENCES audit.orchestration_events(event_id),
    topic text NOT NULL,
    delivery_state text NOT NULL DEFAULT 'PENDING'
        CHECK (delivery_state IN ('PENDING','CLAIMED','RETRY','DELIVERED','DEAD_LETTER')),
    attempt_count integer NOT NULL DEFAULT 0 CHECK (attempt_count >= 0),
    created_at timestamptz NOT NULL DEFAULT now(),
    claimed_at timestamptz NULL,
    claimed_by text NULL,
    lease_expires_at timestamptz NULL,
    next_attempt_at timestamptz NULL,
    delivered_at timestamptz NULL,
    last_error_code text NULL,
    last_error_safe text NULL,
    UNIQUE (event_id, topic),
    CONSTRAINT event_outbox_delivery_fields_ck CHECK (
      (delivery_state = 'DELIVERED' AND delivered_at IS NOT NULL)
      OR delivery_state <> 'DELIVERED'
    )
);

CREATE INDEX IF NOT EXISTS event_outbox_ready_idx
    ON audit.event_outbox (delivery_state, next_attempt_at, created_at)
    WHERE delivery_state IN ('PENDING','RETRY');
CREATE INDEX IF NOT EXISTS event_outbox_lease_idx
    ON audit.event_outbox (lease_expires_at)
    WHERE delivery_state = 'CLAIMED';

COMMIT;
