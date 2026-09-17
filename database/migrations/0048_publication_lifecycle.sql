-- STH M4-022 through M4-031: publication lifecycle controls.
BEGIN;
CREATE TABLE IF NOT EXISTS publication.publication_freezes (
  freeze_id uuid PRIMARY KEY,
  property_id uuid NOT NULL REFERENCES core.properties(property_id),
  report_variant text NOT NULL REFERENCES reference.report_variant(code),
  channel text NULL REFERENCES reference.publication_channel(code),
  reason_code text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  created_by text NOT NULL,
  released_at timestamptz NULL,
  released_by text NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_publication_freeze_active_scope
ON publication.publication_freezes(property_id,report_variant,COALESCE(channel,'*')) WHERE released_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_publication_history_lookup
ON publication.publication_history(property_id,report_variant,channel,report_id,render_id,occurred_at DESC);
COMMIT;
