-- STH M4-018: durable publication staging and pointer-lock support.
BEGIN;
CREATE TABLE IF NOT EXISTS publication.publication_staging (
  staging_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  property_id uuid NOT NULL REFERENCES core.properties(property_id),
  report_variant text NOT NULL REFERENCES reference.report_variant(code),
  channel text NOT NULL REFERENCES reference.publication_channel(code),
  report_id uuid NOT NULL REFERENCES reporting.report_versions(report_id),
  render_id uuid NOT NULL REFERENCES reporting.render_versions(render_id),
  staging_state text NOT NULL DEFAULT 'STAGED' CHECK (staging_state IN ('STAGED','VALIDATING','READY','PUBLISHED','BLOCKED','FAILED','STALE','CANCELLED')),
  requested_by text NOT NULL,
  reason_code text NULL,
  correlation_id uuid NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE(property_id,report_variant,channel,report_id,render_id)
);
CREATE INDEX IF NOT EXISTS idx_publication_staging_ready
ON publication.publication_staging(property_id,report_variant,channel,created_at)
WHERE staging_state IN ('STAGED','VALIDATING','READY');
COMMIT;
