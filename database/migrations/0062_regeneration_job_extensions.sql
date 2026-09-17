-- STH M3-001: guarded state-shape invariants for regeneration jobs.
BEGIN;

ALTER TABLE orchestration.regeneration_jobs
    ADD CONSTRAINT regeneration_jobs_completion_shape_chk
    CHECK (
        (job_state IN ('SUCCEEDED','NO_OP') AND completed_at IS NOT NULL)
        OR job_state NOT IN ('SUCCEEDED','NO_OP')
    );

ALTER TABLE orchestration.regeneration_jobs
    ADD CONSTRAINT regeneration_jobs_lease_shape_chk
    CHECK (
        (job_state IN ('CLAIMED','RUNNING') AND worker_id IS NOT NULL AND lease_expires_at IS NOT NULL)
        OR job_state NOT IN ('CLAIMED','RUNNING')
    );

COMMIT;
