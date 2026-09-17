-- STH M5-001: release-control persistence foundation.
-- Persistence only: policy resolution, membership resolution/freezing, item lifecycle,
-- validation, approval, rollout, rollback and cancellation are implemented by later M5 tickets.
BEGIN;

CREATE TABLE IF NOT EXISTS operations.releases (
  release_id uuid PRIMARY KEY,
  release_name text NULL,
  release_state text NOT NULL REFERENCES reference.release_state(code),
  release_scope jsonb NOT NULL DEFAULT '{}'::jsonb,
  policy_version text NULL,
  membership_fingerprint char(64) NULL CHECK (membership_fingerprint IS NULL OR membership_fingerprint ~ '^[0-9a-f]{64}$'),
  manifest_fingerprint char(64) NULL CHECK (manifest_fingerprint IS NULL OR manifest_fingerprint ~ '^[0-9a-f]{64}$'),
  total_item_count integer NOT NULL DEFAULT 0 CHECK (total_item_count >= 0),
  correlation_id uuid NULL,
  reason_code text NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  created_by text NOT NULL,
  updated_at timestamptz NOT NULL DEFAULT now()
);

-- Frozen manifest persistence is created here so M5-004 can freeze into a durable,
-- one-row-per-release evidence object without changing the storage contract later.
CREATE TABLE IF NOT EXISTS operations.release_manifests (
  release_id uuid PRIMARY KEY REFERENCES operations.releases(release_id),
  membership_fingerprint char(64) NOT NULL CHECK (membership_fingerprint ~ '^[0-9a-f]{64}$'),
  manifest_fingerprint char(64) NOT NULL CHECK (manifest_fingerprint ~ '^[0-9a-f]{64}$'),
  manifest_payload jsonb NOT NULL,
  frozen_at timestamptz NOT NULL DEFAULT now(),
  frozen_by text NOT NULL
);

-- Release items persist exact fleet targets. M5-005 owns the lifecycle semantics;
-- M5-001 deliberately does not define the transition registry for item_state.
CREATE TABLE IF NOT EXISTS operations.release_items (
  release_item_id uuid PRIMARY KEY,
  release_id uuid NOT NULL REFERENCES operations.releases(release_id),
  property_id uuid NOT NULL REFERENCES core.properties(property_id),
  report_variant text NOT NULL REFERENCES reference.report_variant(code),
  channel text NULL REFERENCES reference.publication_channel(code),
  membership_ordinal integer NOT NULL CHECK (membership_ordinal > 0),
  item_state text NOT NULL DEFAULT 'PENDING' CHECK (length(btrim(item_state)) > 0),
  target_snapshot_id uuid NULL REFERENCES snapshot.intelligence_snapshots(snapshot_id),
  target_report_id uuid NULL REFERENCES reporting.report_versions(report_id),
  target_render_id uuid NULL REFERENCES reporting.render_versions(render_id),
  target_semantic_fingerprint char(64) NULL CHECK (target_semantic_fingerprint IS NULL OR target_semantic_fingerprint ~ '^[0-9a-f]{64}$'),
  target_presentation_fingerprint char(64) NULL CHECK (target_presentation_fingerprint IS NULL OR target_presentation_fingerprint ~ '^[0-9a-f]{64}$'),
  last_error_code text NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE(release_id, property_id, report_variant, channel),
  UNIQUE(release_id, membership_ordinal)
);

CREATE INDEX IF NOT EXISTS idx_releases_state_created
  ON operations.releases(release_state, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_release_items_release_state
  ON operations.release_items(release_id, item_state, membership_ordinal);
CREATE INDEX IF NOT EXISTS idx_release_items_property
  ON operations.release_items(property_id, report_variant, channel);
CREATE INDEX IF NOT EXISTS idx_release_items_snapshot
  ON operations.release_items(target_snapshot_id) WHERE target_snapshot_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_release_items_report
  ON operations.release_items(target_report_id) WHERE target_report_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_release_items_render
  ON operations.release_items(target_render_id) WHERE target_render_id IS NOT NULL;

COMMIT;
