-- STH M3-005/M3-006: retry-ready claim and lease recovery indexes.
BEGIN;
CREATE INDEX IF NOT EXISTS regeneration_jobs_retry_ready_idx
ON orchestration.regeneration_jobs (next_retry_at, priority_score DESC, queued_at ASC, job_id ASC)
WHERE job_state='RETRY_WAIT';
CREATE INDEX IF NOT EXISTS regeneration_jobs_worker_lease_idx
ON orchestration.regeneration_jobs (worker_id, lease_expires_at)
WHERE job_state IN ('CLAIMED','RUNNING');
COMMIT;
