-- STH M7-011 through M7-013: shadow acceptance, go-live stop evidence, and limited approval.
BEGIN;
CREATE TABLE IF NOT EXISTS certification.production_shadow_acceptance (
  production_certification_id uuid PRIMARY KEY REFERENCES certification.production_runs(production_certification_id),
  policy_version text NOT NULL,
  acceptance_status text NOT NULL CHECK (acceptance_status IN ('PASS','FAIL')),
  reason_codes jsonb NOT NULL DEFAULT '[]'::jsonb,
  accepted_cycle_ids jsonb NOT NULL DEFAULT '[]'::jsonb,
  latest_shadow_cycle_id uuid NULL REFERENCES certification.production_shadow_cycles(shadow_cycle_id),
  manual_audit_sample_id uuid NULL REFERENCES certification.production_manual_audit_samples(manual_audit_sample_id),
  acceptance_fingerprint char(64) NOT NULL CHECK (acceptance_fingerprint ~ '^[0-9a-f]{64}$'),
  evaluated_by text NOT NULL,
  evaluated_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS certification.production_go_live_stop_results (
  production_certification_id uuid PRIMARY KEY REFERENCES certification.production_runs(production_certification_id),
  policy_version text NOT NULL,
  stop_status text NOT NULL CHECK (stop_status IN ('CLEAR','STOP')),
  blocking_conditions jsonb NOT NULL DEFAULT '[]'::jsonb,
  evidence_fingerprint char(64) NOT NULL CHECK (evidence_fingerprint ~ '^[0-9a-f]{64}$'),
  evaluated_by text NOT NULL,
  evaluated_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS certification.production_limited_approvals (
  limited_approval_id uuid PRIMARY KEY,
  production_certification_id uuid NOT NULL UNIQUE REFERENCES certification.production_runs(production_certification_id),
  policy_version text NOT NULL,
  approval_type text NOT NULL CHECK (approval_type='LIMITED'),
  candidate_fingerprint char(64) NOT NULL CHECK (candidate_fingerprint ~ '^[0-9a-f]{64}$'),
  pilot_membership_fingerprint char(64) NOT NULL CHECK (pilot_membership_fingerprint ~ '^[0-9a-f]{64}$'),
  max_properties integer NOT NULL CHECK (max_properties > 0),
  allowed_variants jsonb NOT NULL,
  shadow_acceptance_fingerprint char(64) NOT NULL CHECK (shadow_acceptance_fingerprint ~ '^[0-9a-f]{64}$'),
  stop_condition_fingerprint char(64) NOT NULL CHECK (stop_condition_fingerprint ~ '^[0-9a-f]{64}$'),
  issued_at timestamptz NOT NULL,
  expires_at timestamptz NOT NULL CHECK (expires_at > issued_at),
  approval_fingerprint char(64) NOT NULL UNIQUE CHECK (approval_fingerprint ~ '^[0-9a-f]{64}$'),
  approved_by text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE OR REPLACE FUNCTION certification.prevent_go_live_evidence_mutation() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'go-live certification evidence is immutable'; END $$;
DROP TRIGGER IF EXISTS trg_shadow_acceptance_immutable ON certification.production_shadow_acceptance;
CREATE TRIGGER trg_shadow_acceptance_immutable BEFORE UPDATE OR DELETE ON certification.production_shadow_acceptance FOR EACH ROW EXECUTE FUNCTION certification.prevent_go_live_evidence_mutation();
DROP TRIGGER IF EXISTS trg_go_live_stop_immutable ON certification.production_go_live_stop_results;
CREATE TRIGGER trg_go_live_stop_immutable BEFORE UPDATE OR DELETE ON certification.production_go_live_stop_results FOR EACH ROW EXECUTE FUNCTION certification.prevent_go_live_evidence_mutation();
DROP TRIGGER IF EXISTS trg_limited_approval_immutable ON certification.production_limited_approvals;
CREATE TRIGGER trg_limited_approval_immutable BEFORE UPDATE OR DELETE ON certification.production_limited_approvals FOR EACH ROW EXECUTE FUNCTION certification.prevent_go_live_evidence_mutation();
COMMIT;
