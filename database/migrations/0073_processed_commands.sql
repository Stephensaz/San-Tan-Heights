-- STH M1-008: Processed command ledger for command idempotency.
BEGIN;

CREATE TABLE IF NOT EXISTS audit.processed_commands (
    processed_command_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    command_id uuid NOT NULL,
    service_name text NOT NULL,
    command_type text NOT NULL,
    idempotency_key text NOT NULL,
    request_hash char(64) NOT NULL CHECK (request_hash ~ '^[0-9a-f]{64}$'),
    result_status text NOT NULL CHECK (result_status IN ('APPLIED','REJECTED','BLOCKED','NO_OP','CONFLICT','FAILED')),
    result_payload jsonb NOT NULL DEFAULT '{}'::jsonb,
    processed_at timestamptz NOT NULL DEFAULT now(),
    correlation_id uuid NOT NULL,
    UNIQUE (service_name, idempotency_key),
    UNIQUE (command_id)
);

CREATE INDEX IF NOT EXISTS processed_commands_command_type_idx
    ON audit.processed_commands (command_type, processed_at DESC);
CREATE INDEX IF NOT EXISTS processed_commands_correlation_idx
    ON audit.processed_commands (correlation_id);

COMMIT;
