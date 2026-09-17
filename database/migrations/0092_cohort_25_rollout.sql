-- STH M7-014 through M7-016: frozen cohort membership, Cohort 25 deployment, and cohort evidence certification.
BEGIN;
CREATE TABLE IF NOT EXISTS certification.production_cohorts (
  cohort_id uuid PRIMARY KEY,
  production_certification_id uuid NOT NULL REFERENCES certification.production_runs(production_certification_id),
  cohort_code text NOT NULL,
  policy_version text NOT NULL,
  candidate_fingerprint char(64) NOT NULL CHECK (candidate_fingerprint ~ '^[0-9a-f]{64}$'),
  pilot_membership_fingerprint char(64) NOT NULL CHECK (pilot_membership_fingerprint ~ '^[0-9a-f]{64}$'),
  limited_approval_id uuid NOT NULL REFERENCES certification.production_limited_approvals(limited_approval_id),
  limited_approval_fingerprint char(64) NOT NULL CHECK (limited_approval_fingerprint ~ '^[0-9a-f]{64}$'),
  property_count integer NOT NULL CHECK (property_count > 0),
  allowed_variants jsonb NOT NULL,
  membership_fingerprint char(64) NOT NULL UNIQUE CHECK (membership_fingerprint ~ '^[0-9a-f]{64}$'),
  frozen_by text NOT NULL,
  frozen_at timestamptz NOT NULL,
  UNIQUE (production_certification_id, cohort_code)
);
CREATE TABLE IF NOT EXISTS certification.production_cohort_members (
  cohort_id uuid NOT NULL REFERENCES certification.production_cohorts(cohort_id),
  membership_ordinal integer NOT NULL CHECK (membership_ordinal > 0),
  property_id uuid NOT NULL,
  PRIMARY KEY (cohort_id, membership_ordinal),
  UNIQUE (cohort_id, property_id)
);
CREATE TABLE IF NOT EXISTS certification.production_cohort_deployments (
  cohort_deployment_id uuid PRIMARY KEY,
  cohort_id uuid NOT NULL UNIQUE REFERENCES certification.production_cohorts(cohort_id),
  production_certification_id uuid NOT NULL REFERENCES certification.production_runs(production_certification_id),
  candidate_fingerprint char(64) NOT NULL CHECK (candidate_fingerprint ~ '^[0-9a-f]{64}$'),
  limited_approval_fingerprint char(64) NOT NULL CHECK (limited_approval_fingerprint ~ '^[0-9a-f]{64}$'),
  membership_fingerprint char(64) NOT NULL CHECK (membership_fingerprint ~ '^[0-9a-f]{64}$'),
  deployment_status text NOT NULL CHECK (deployment_status IN ('PASS','FAIL')),
  deployment_fingerprint char(64) NOT NULL UNIQUE CHECK (deployment_fingerprint ~ '^[0-9a-f]{64}$'),
  deployed_by text NOT NULL,
  started_at timestamptz NOT NULL,
  completed_at timestamptz NOT NULL CHECK (completed_at >= started_at)
);
CREATE TABLE IF NOT EXISTS certification.production_cohort_deployment_items (
  cohort_deployment_id uuid NOT NULL REFERENCES certification.production_cohort_deployments(cohort_deployment_id),
  membership_ordinal integer NOT NULL CHECK (membership_ordinal > 0),
  property_id uuid NOT NULL,
  deployment_status text NOT NULL CHECK (deployment_status IN ('PASS','FAIL')),
  evidence_hash char(64) NOT NULL CHECK (evidence_hash ~ '^[0-9a-f]{64}$'),
  detail jsonb NOT NULL DEFAULT '{}'::jsonb,
  PRIMARY KEY (cohort_deployment_id, membership_ordinal),
  UNIQUE (cohort_deployment_id, property_id)
);
CREATE TABLE IF NOT EXISTS certification.production_cohort_certifications (
  cohort_certification_id uuid PRIMARY KEY,
  production_certification_id uuid NOT NULL REFERENCES certification.production_runs(production_certification_id),
  cohort_id uuid NOT NULL REFERENCES certification.production_cohorts(cohort_id),
  cohort_deployment_id uuid NOT NULL UNIQUE REFERENCES certification.production_cohort_deployments(cohort_deployment_id),
  policy_version text NOT NULL,
  certification_status text NOT NULL CHECK (certification_status IN ('PASS','FAIL')),
  reason_codes jsonb NOT NULL DEFAULT '[]'::jsonb,
  expected_item_count integer NOT NULL CHECK (expected_item_count >= 0),
  deployed_item_count integer NOT NULL CHECK (deployed_item_count >= 0),
  passed_item_count integer NOT NULL CHECK (passed_item_count >= 0),
  membership_fingerprint char(64) NOT NULL CHECK (membership_fingerprint ~ '^[0-9a-f]{64}$'),
  deployment_fingerprint char(64) NOT NULL CHECK (deployment_fingerprint ~ '^[0-9a-f]{64}$'),
  certification_fingerprint char(64) NOT NULL UNIQUE CHECK (certification_fingerprint ~ '^[0-9a-f]{64}$'),
  certified_by text NOT NULL,
  certified_at timestamptz NOT NULL DEFAULT now()
);
CREATE OR REPLACE FUNCTION certification.prevent_cohort_rollout_evidence_mutation() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'production cohort rollout evidence is immutable'; END $$;
DROP TRIGGER IF EXISTS trg_production_cohorts_immutable ON certification.production_cohorts;
CREATE TRIGGER trg_production_cohorts_immutable BEFORE UPDATE OR DELETE ON certification.production_cohorts FOR EACH ROW EXECUTE FUNCTION certification.prevent_cohort_rollout_evidence_mutation();
DROP TRIGGER IF EXISTS trg_production_cohort_members_immutable ON certification.production_cohort_members;
CREATE TRIGGER trg_production_cohort_members_immutable BEFORE UPDATE OR DELETE ON certification.production_cohort_members FOR EACH ROW EXECUTE FUNCTION certification.prevent_cohort_rollout_evidence_mutation();
DROP TRIGGER IF EXISTS trg_production_cohort_deployments_immutable ON certification.production_cohort_deployments;
CREATE TRIGGER trg_production_cohort_deployments_immutable BEFORE UPDATE OR DELETE ON certification.production_cohort_deployments FOR EACH ROW EXECUTE FUNCTION certification.prevent_cohort_rollout_evidence_mutation();
DROP TRIGGER IF EXISTS trg_production_cohort_deployment_items_immutable ON certification.production_cohort_deployment_items;
CREATE TRIGGER trg_production_cohort_deployment_items_immutable BEFORE UPDATE OR DELETE ON certification.production_cohort_deployment_items FOR EACH ROW EXECUTE FUNCTION certification.prevent_cohort_rollout_evidence_mutation();
DROP TRIGGER IF EXISTS trg_production_cohort_certifications_immutable ON certification.production_cohort_certifications;
CREATE TRIGGER trg_production_cohort_certifications_immutable BEFORE UPDATE OR DELETE ON certification.production_cohort_certifications FOR EACH ROW EXECUTE FUNCTION certification.prevent_cohort_rollout_evidence_mutation();
COMMIT;
