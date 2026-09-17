-- STH M7-001: production-certification persistence foundation.
-- Persistence only. Candidate freezing, manifest pinning, environment/config checks,
-- shadow operation, approvals, cohort rollout, rollback, revocation, and final approval
-- are implemented by later M7 tickets.
BEGIN;

CREATE TABLE IF NOT EXISTS certification.production_runs (
  production_certification_id uuid PRIMARY KEY,
  system_certification_run_id uuid NOT NULL REFERENCES certification.runs(certification_run_id),
  contract_version text NOT NULL,
  candidate_version text NOT NULL,
  candidate_fingerprint char(64) NOT NULL CHECK (candidate_fingerprint ~ '^[0-9a-f]{64}$'),
  run_state text NOT NULL DEFAULT 'CREATED'
    CHECK (run_state IN ('CREATED','IN_PROGRESS','BLOCKED','PASSED','FAILED','REVOKED')),
  verdict text NULL CHECK (verdict IS NULL OR verdict IN ('GO','NO_GO')),
  correlation_id uuid NULL,
  created_by text NOT NULL,
  started_at timestamptz NULL,
  completed_at timestamptz NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE(system_certification_run_id, candidate_fingerprint)
);

CREATE TABLE IF NOT EXISTS certification.production_evidence (
  production_evidence_id uuid PRIMARY KEY,
  production_certification_id uuid NOT NULL
    REFERENCES certification.production_runs(production_certification_id),
  evidence_type text NOT NULL CHECK (length(btrim(evidence_type)) > 0),
  subject_key text NOT NULL CHECK (length(btrim(subject_key)) > 0),
  evidence_hash char(64) NOT NULL CHECK (evidence_hash ~ '^[0-9a-f]{64}$'),
  evidence_payload jsonb NOT NULL DEFAULT '{}'::jsonb,
  source_uri text NULL,
  captured_by text NOT NULL,
  captured_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE(production_certification_id, evidence_type, subject_key, evidence_hash)
);

CREATE TABLE IF NOT EXISTS certification.production_check_results (
  production_check_result_id uuid PRIMARY KEY,
  production_certification_id uuid NOT NULL
    REFERENCES certification.production_runs(production_certification_id),
  stage_code text NOT NULL CHECK (length(btrim(stage_code)) > 0),
  check_code text NOT NULL CHECK (length(btrim(check_code)) > 0),
  status text NOT NULL CHECK (status IN ('PASS','FAIL','BLOCKED','NOT_RUN')),
  evidence_hash char(64) NOT NULL CHECK (evidence_hash ~ '^[0-9a-f]{64}$'),
  detail jsonb NOT NULL DEFAULT '{}'::jsonb,
  observed_by text NOT NULL,
  observed_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE(production_certification_id, stage_code, check_code)
);

CREATE INDEX IF NOT EXISTS idx_production_runs_state_created
  ON certification.production_runs(run_state, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_production_evidence_run_type
  ON certification.production_evidence(production_certification_id, evidence_type, captured_at);
CREATE INDEX IF NOT EXISTS idx_production_checks_run_stage
  ON certification.production_check_results(production_certification_id, stage_code, check_code);

CREATE OR REPLACE FUNCTION certification.prevent_production_evidence_mutation()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'production certification evidence is append-only';
END $$;

DROP TRIGGER IF EXISTS trg_production_evidence_immutable ON certification.production_evidence;
CREATE TRIGGER trg_production_evidence_immutable
  BEFORE UPDATE OR DELETE ON certification.production_evidence
  FOR EACH ROW EXECUTE FUNCTION certification.prevent_production_evidence_mutation();

DROP TRIGGER IF EXISTS trg_production_check_results_immutable ON certification.production_check_results;
CREATE TRIGGER trg_production_check_results_immutable
  BEFORE UPDATE OR DELETE ON certification.production_check_results
  FOR EACH ROW EXECUTE FUNCTION certification.prevent_production_evidence_mutation();

COMMIT;
