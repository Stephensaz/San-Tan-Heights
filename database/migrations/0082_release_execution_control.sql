-- STH M5-005..M5-014: release execution evidence and lifecycle constraints.
BEGIN;

ALTER TABLE operations.release_items
  DROP CONSTRAINT IF EXISTS release_items_item_state_check;
ALTER TABLE operations.release_items
  ADD CONSTRAINT release_items_item_state_check CHECK (item_state IN (
    'PENDING','GENERATION_QUEUED','GENERATING','GENERATED','VALIDATED','STAGED','APPROVED',
    'PUBLISHING','PUBLISHED','BLOCKED','FAILED','ROLLED_BACK','CANCELLED'
  ));

CREATE TABLE IF NOT EXISTS operations.release_item_history (
  history_id bigserial PRIMARY KEY,
  release_item_id uuid NOT NULL REFERENCES operations.release_items(release_item_id),
  release_id uuid NOT NULL REFERENCES operations.releases(release_id),
  from_state text NULL,
  to_state text NOT NULL,
  reason_code text NULL,
  actor text NOT NULL,
  correlation_id uuid NULL,
  occurred_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_release_item_history_release
  ON operations.release_item_history(release_id, occurred_at, history_id);

CREATE TABLE IF NOT EXISTS operations.release_validation_results (
  validation_id bigserial PRIMARY KEY,
  release_id uuid NOT NULL REFERENCES operations.releases(release_id),
  release_item_id uuid NOT NULL REFERENCES operations.release_items(release_item_id),
  validation_status text NOT NULL CHECK (validation_status IN ('PASS','FAIL')),
  reason_code text NULL,
  validator_version text NOT NULL,
  evidence jsonb NOT NULL DEFAULT '{}'::jsonb,
  validated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE(release_item_id, validator_version)
);

CREATE TABLE IF NOT EXISTS operations.release_approvals (
  approval_id bigserial PRIMARY KEY,
  release_id uuid NOT NULL REFERENCES operations.releases(release_id),
  manifest_fingerprint char(64) NOT NULL CHECK (manifest_fingerprint ~ '^[0-9a-f]{64}$'),
  decision text NOT NULL CHECK (decision IN ('APPROVED','REJECTED')),
  approved_by text NOT NULL,
  reason_code text NULL,
  decided_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_release_approvals_release
  ON operations.release_approvals(release_id, decided_at DESC);

COMMIT;
