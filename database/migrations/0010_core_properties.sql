-- STH M2-002 prerequisite: canonical property anchor for snapshots.
BEGIN;
CREATE TABLE IF NOT EXISTS core.properties (
    property_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    canonical_key text NOT NULL UNIQUE,
    status text NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE','INACTIVE','BLOCKED')),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);
COMMIT;
