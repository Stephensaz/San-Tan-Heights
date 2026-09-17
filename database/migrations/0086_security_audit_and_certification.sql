CREATE SCHEMA IF NOT EXISTS certification;

CREATE TABLE IF NOT EXISTS audit.security_events (
  security_event_id uuid PRIMARY KEY,
  event_type text NOT NULL,
  occurred_at timestamptz NOT NULL,
  actor_type text NOT NULL,
  actor_id text NOT NULL,
  outcome text NOT NULL CHECK (outcome IN ('ALLOW','DENY','SUCCESS','FAILURE','EXPIRED','REVOKED')),
  reason_code text NOT NULL,
  property_id uuid NULL,
  incident_id uuid NULL,
  correlation_id uuid NULL,
  evidence_hash text NULL CHECK (evidence_hash IS NULL OR evidence_hash ~ '^[0-9a-f]{64}$')
);
CREATE INDEX IF NOT EXISTS idx_security_events_type_time ON audit.security_events(event_type, occurred_at DESC);
CREATE INDEX IF NOT EXISTS idx_security_events_property_time ON audit.security_events(property_id, occurred_at DESC) WHERE property_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS certification.runs (
  certification_run_id uuid PRIMARY KEY,
  candidate_version text NOT NULL,
  contract_version text NOT NULL,
  candidate_fingerprint text NOT NULL CHECK (candidate_fingerprint ~ '^[0-9a-f]{64}$'),
  run_state text NOT NULL CHECK (run_state IN ('CREATED','RUNNING','PASSED','FAILED')),
  verdict text NULL CHECK (verdict IS NULL OR verdict IN ('GO','NO_GO')),
  started_at timestamptz NULL,
  completed_at timestamptz NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS certification.scenario_results (
  certification_run_id uuid NOT NULL REFERENCES certification.runs(certification_run_id),
  scenario_id text NOT NULL,
  status text NOT NULL CHECK (status IN ('PASS','FAIL','ERROR','NOT_RUN')),
  evidence_hash text NOT NULL CHECK (evidence_hash ~ '^[0-9a-f]{64}$'),
  detail jsonb NOT NULL DEFAULT '{}'::jsonb,
  PRIMARY KEY(certification_run_id, scenario_id)
);
CREATE TABLE IF NOT EXISTS certification.metric_results (
  certification_run_id uuid NOT NULL REFERENCES certification.runs(certification_run_id),
  metric_id text NOT NULL,
  observed_value bigint NOT NULL,
  maximum_allowed bigint NOT NULL,
  status text NOT NULL CHECK (status IN ('PASS','FAIL')),
  PRIMARY KEY(certification_run_id, metric_id)
);

CREATE OR REPLACE FUNCTION certification.prevent_certification_evidence_mutation() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'certification evidence is append-only'; END $$;
DROP TRIGGER IF EXISTS trg_cert_scenario_immutable ON certification.scenario_results;
CREATE TRIGGER trg_cert_scenario_immutable BEFORE UPDATE OR DELETE ON certification.scenario_results FOR EACH ROW EXECUTE FUNCTION certification.prevent_certification_evidence_mutation();
DROP TRIGGER IF EXISTS trg_cert_metric_immutable ON certification.metric_results;
CREATE TRIGGER trg_cert_metric_immutable BEFORE UPDATE OR DELETE ON certification.metric_results FOR EACH ROW EXECUTE FUNCTION certification.prevent_certification_evidence_mutation();
