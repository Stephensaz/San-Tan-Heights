-- STH M4-015 through M4-017: explicit semantic-current and per-channel publication pointers.
BEGIN;
CREATE TABLE IF NOT EXISTS reference.publication_channel (
  code text PRIMARY KEY,
  description text NOT NULL DEFAULT ''
);
INSERT INTO reference.publication_channel(code) VALUES ('WEB'),('PDF_DOWNLOAD'),('PRINT') ON CONFLICT (code) DO NOTHING;

CREATE TABLE IF NOT EXISTS publication.report_current (
  property_id uuid NOT NULL REFERENCES core.properties(property_id),
  report_variant text NOT NULL REFERENCES reference.report_variant(code),
  report_id uuid NOT NULL REFERENCES reporting.report_versions(report_id),
  pointer_version bigint NOT NULL DEFAULT 1 CHECK (pointer_version > 0),
  updated_at timestamptz NOT NULL DEFAULT now(),
  updated_by text NOT NULL,
  PRIMARY KEY(property_id, report_variant)
);

CREATE TABLE IF NOT EXISTS publication.channel_pointers (
  property_id uuid NOT NULL REFERENCES core.properties(property_id),
  report_variant text NOT NULL REFERENCES reference.report_variant(code),
  channel text NOT NULL REFERENCES reference.publication_channel(code),
  report_id uuid NOT NULL REFERENCES reporting.report_versions(report_id),
  render_id uuid NOT NULL REFERENCES reporting.render_versions(render_id),
  pointer_version bigint NOT NULL DEFAULT 1 CHECK (pointer_version > 0),
  updated_at timestamptz NOT NULL DEFAULT now(),
  updated_by text NOT NULL,
  PRIMARY KEY(property_id, report_variant, channel)
);

CREATE TABLE IF NOT EXISTS publication.publication_history (
  publication_history_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  property_id uuid NOT NULL REFERENCES core.properties(property_id),
  report_variant text NOT NULL REFERENCES reference.report_variant(code),
  channel text NULL REFERENCES reference.publication_channel(code),
  report_id uuid NOT NULL REFERENCES reporting.report_versions(report_id),
  render_id uuid NULL REFERENCES reporting.render_versions(render_id),
  action text NOT NULL,
  reason_code text NULL,
  correlation_id uuid NULL,
  occurred_at timestamptz NOT NULL DEFAULT now(),
  actor text NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_publication_history_property_variant
ON publication.publication_history(property_id,report_variant,occurred_at DESC);
CREATE INDEX IF NOT EXISTS idx_publication_history_render
ON publication.publication_history(render_id) WHERE render_id IS NOT NULL;
COMMIT;
