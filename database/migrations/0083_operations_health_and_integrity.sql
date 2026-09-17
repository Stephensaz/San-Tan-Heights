-- STH M5-015..M5-022: operational health/read-model and integrity sweep persistence.
BEGIN;
CREATE TABLE IF NOT EXISTS operations.integrity_sweep_runs (
  sweep_run_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  sweep_type text NOT NULL CHECK (sweep_type IN ('PUBLICATION_POINTER','ORPHAN','STUCK_JOB','RELEASE')),
  started_at timestamptz NOT NULL DEFAULT now(), completed_at timestamptz NULL,
  status text NOT NULL CHECK (status IN ('RUNNING','PASS','FAIL')), checked_count integer NOT NULL DEFAULT 0,
  finding_count integer NOT NULL DEFAULT 0, correlation_id uuid NULL
);
CREATE TABLE IF NOT EXISTS operations.integrity_findings (
  finding_id bigserial PRIMARY KEY, sweep_run_id uuid NOT NULL REFERENCES operations.integrity_sweep_runs(sweep_run_id),
  rule_id text NOT NULL, entity_type text NOT NULL, entity_id text NOT NULL,
  finding_status text NOT NULL CHECK (finding_status IN ('PASS','FAIL')), detail text NOT NULL,
  detected_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_integrity_findings_rule ON operations.integrity_findings(rule_id,detected_at DESC);
CREATE INDEX IF NOT EXISTS idx_integrity_findings_entity ON operations.integrity_findings(entity_type,entity_id,detected_at DESC);

CREATE OR REPLACE VIEW operations.property_health_current AS
SELECT p.property_id,
       CASE WHEN cs.current_snapshot_id IS NULL THEN 'CRITICAL' ELSE 'HEALTHY' END AS health_status,
       cs.current_snapshot_id AS current_snapshot_id,
       COALESCE(j.open_job_count,0) AS open_job_count,
       0::bigint AS pointer_violation_count, 0::bigint AS orphan_count, 0::bigint AS stuck_job_count, 0::bigint AS release_failure_count
FROM core.properties p
LEFT JOIN snapshot.current_snapshot_view cs ON cs.property_id=p.property_id
LEFT JOIN (
  SELECT property_id,count(*) AS open_job_count FROM orchestration.regeneration_jobs
  WHERE job_state IN ('QUEUED','CLAIMED','RUNNING','RETRY_READY') GROUP BY property_id
) j ON j.property_id=p.property_id;

CREATE OR REPLACE VIEW operations.fleet_health_current AS
SELECT count(*)::bigint AS total_properties,
       count(*) FILTER (WHERE health_status='HEALTHY')::bigint AS healthy_count,
       count(*) FILTER (WHERE health_status='DEGRADED')::bigint AS degraded_count,
       count(*) FILTER (WHERE health_status='CRITICAL')::bigint AS critical_count,
       count(*) FILTER (WHERE health_status='UNKNOWN')::bigint AS unknown_count,
       COALESCE(sum(open_job_count),0)::bigint AS open_job_count,
       (SELECT count(*) FROM operations.releases WHERE release_state IN ('ASSEMBLING','GENERATION_READY','GENERATING','VALIDATING','STAGED','APPROVED','PUBLISHING','PARTIAL_FAILURE','ROLLING_BACK'))::bigint AS active_release_count
FROM operations.property_health_current;
COMMIT;
