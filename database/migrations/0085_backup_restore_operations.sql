-- STH M5-027..M5-030: backup/restore verification, post-restore global freeze, dashboard projection.
BEGIN;
CREATE TABLE IF NOT EXISTS operations.backup_verifications (
  verification_id uuid PRIMARY KEY,
  backup_id text NOT NULL,
  backup_type text NOT NULL CHECK (backup_type IN ('FULL','LOGICAL','PHYSICAL')),
  source_environment text NOT NULL,
  expected_sha256 char(64) NOT NULL CHECK (expected_sha256 ~ '^[0-9a-f]{64}$'),
  observed_sha256 char(64) NOT NULL CHECK (observed_sha256 ~ '^[0-9a-f]{64}$'),
  expected_size_bytes bigint NOT NULL CHECK (expected_size_bytes > 0),
  observed_size_bytes bigint NOT NULL CHECK (observed_size_bytes > 0),
  manifest_fingerprint char(64) NOT NULL CHECK (manifest_fingerprint ~ '^[0-9a-f]{64}$'),
  verification_status text NOT NULL CHECK (verification_status IN ('VERIFIED','FAILED')),
  reason_codes jsonb NOT NULL DEFAULT '[]'::jsonb,
  verifier_version text NOT NULL,
  verified_by text NOT NULL,
  verified_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE(backup_id,observed_sha256,manifest_fingerprint)
);

CREATE TABLE IF NOT EXISTS operations.restore_verifications (
  restore_verification_id uuid PRIMARY KEY,
  backup_verification_id uuid NOT NULL REFERENCES operations.backup_verifications(verification_id),
  restored_environment text NOT NULL,
  schema_version text NOT NULL,
  expected_manifest_fingerprint char(64) NOT NULL CHECK (expected_manifest_fingerprint ~ '^[0-9a-f]{64}$'),
  observed_manifest_fingerprint char(64) NOT NULL CHECK (observed_manifest_fingerprint ~ '^[0-9a-f]{64}$'),
  integrity_check_status text NOT NULL CHECK (integrity_check_status IN ('PASS','FAIL')),
  row_count_check_status text NOT NULL CHECK (row_count_check_status IN ('PASS','FAIL')),
  verification_status text NOT NULL CHECK (verification_status IN ('VERIFIED','FAILED')),
  reason_codes jsonb NOT NULL DEFAULT '[]'::jsonb,
  verifier_version text NOT NULL,
  verified_by text NOT NULL,
  verified_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS operations.global_publication_freezes (
  freeze_id uuid PRIMARY KEY,
  reason_code text NOT NULL REFERENCES reference.reason_code(code),
  restore_verification_id uuid NOT NULL REFERENCES operations.restore_verifications(restore_verification_id),
  created_by text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  released_by text NULL,
  released_at timestamptz NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_global_publication_freeze_active
ON operations.global_publication_freezes((1)) WHERE released_at IS NULL;

CREATE OR REPLACE VIEW operations.operations_dashboard_current AS
SELECT
  CASE WHEN COALESCE(f.critical_count,0)>0 OR COALESCE(i.critical_incident_count,0)>0 THEN 'CRITICAL'
       WHEN COALESCE(f.degraded_count,0)>0 OR COALESCE(i.open_incident_count,0)>0 THEN 'DEGRADED'
       WHEN COALESCE(f.total_properties,0)>0 THEN 'HEALTHY' ELSE 'UNKNOWN' END AS fleet_status,
  COALESCE(f.total_properties,0)::bigint AS total_properties,
  COALESCE(f.healthy_count,0)::bigint AS healthy_count,
  COALESCE(f.degraded_count,0)::bigint AS degraded_count,
  COALESCE(f.critical_count,0)::bigint AS critical_count,
  COALESCE(f.unknown_count,0)::bigint AS unknown_count,
  COALESCE(f.open_job_count,0)::bigint AS open_job_count,
  COALESCE(f.active_release_count,0)::bigint AS active_release_count,
  COALESCE(i.open_incident_count,0)::bigint AS open_incident_count,
  COALESCE(i.critical_incident_count,0)::bigint AS critical_incident_count,
  EXISTS(SELECT 1 FROM operations.global_publication_freezes g WHERE g.released_at IS NULL) AS active_global_publication_freeze,
  (SELECT verification_status FROM operations.backup_verifications ORDER BY verified_at DESC LIMIT 1) AS latest_backup_status,
  (SELECT verification_status FROM operations.restore_verifications ORDER BY verified_at DESC LIMIT 1) AS latest_restore_status
FROM operations.fleet_health_current f
CROSS JOIN LATERAL (
  SELECT count(*) FILTER(WHERE incident_state IN ('OPEN','CONTAINED','RECOVERING')) AS open_incident_count,
         count(*) FILTER(WHERE severity='CRITICAL' AND incident_state IN ('OPEN','CONTAINED','RECOVERING')) AS critical_incident_count
  FROM operations.incidents
) i;
COMMIT;
