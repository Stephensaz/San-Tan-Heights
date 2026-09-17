-- STH M1-013: persistence-only test entity for the governed state-adapter framework.
BEGIN;

CREATE TABLE IF NOT EXISTS operations.kernel_test_entities (
    entity_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    state text NOT NULL,
    state_version bigint NOT NULL DEFAULT 1 CHECK (state_version > 0),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT kernel_test_entities_state_fk
      FOREIGN KEY (state) REFERENCES reference.content_state(code)
);

CREATE INDEX IF NOT EXISTS idx_kernel_test_entities_state
    ON operations.kernel_test_entities(state);

COMMIT;
