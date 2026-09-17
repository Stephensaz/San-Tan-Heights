-- STH M3-001: queue and lookup indexes.
BEGIN;

CREATE INDEX IF NOT EXISTS regeneration_jobs_claim_idx
ON orchestration.regeneration_jobs (priority_score DESC, queued_at ASC, job_id ASC)
WHERE job_state IN ('QUEUED','RETRY_WAIT');

CREATE INDEX IF NOT EXISTS regeneration_jobs_property_variant_idx
ON orchestration.regeneration_jobs (property_id, report_variant, queued_at DESC);

CREATE INDEX IF NOT EXISTS regeneration_jobs_target_snapshot_idx
ON orchestration.regeneration_jobs (target_snapshot_id);

CREATE INDEX IF NOT EXISTS regeneration_jobs_lease_idx
ON orchestration.regeneration_jobs (lease_expires_at)
WHERE job_state IN ('CLAIMED','RUNNING');

CREATE UNIQUE INDEX IF NOT EXISTS regeneration_jobs_one_active_target_uq
ON orchestration.regeneration_jobs (property_id, report_variant, job_target_key)
WHERE job_state IN ('QUEUED','CLAIMED','RUNNING','RETRY_WAIT');

COMMIT;
