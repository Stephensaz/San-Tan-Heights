-- M7-023 through M7-026: rollback/containment, evidence bundle, revocation, FULL_APPROVAL.
CREATE TABLE IF NOT EXISTS certification.rollback_containment_runs (
  rollback_run_id uuid PRIMARY KEY,
  production_certification_id uuid NOT NULL REFERENCES certification.production_runs(production_certification_id),
  stage_code text NOT NULL,
  candidate_fingerprint char(64) NOT NULL,
  rollback_baseline_id uuid NOT NULL REFERENCES certification.rollback_baselines(rollback_baseline_id),
  rollback_baseline_fingerprint char(64) NOT NULL,
  status text NOT NULL CHECK (status IN ('PASS','CONTAINED')),
  run_fingerprint char(64) NOT NULL UNIQUE,
  executed_by text NOT NULL,
  reason_code text NOT NULL,
  executed_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS certification.rollback_containment_items (
  rollback_run_id uuid NOT NULL REFERENCES certification.rollback_containment_runs(rollback_run_id),
  property_id uuid NOT NULL REFERENCES core.properties(property_id),
  variant text NOT NULL,
  channel text NOT NULL,
  status text NOT NULL CHECK (status IN ('PASS','CONTAINED')),
  evidence_hash char(64) NOT NULL,
  detail jsonb NOT NULL DEFAULT '{}'::jsonb,
  PRIMARY KEY (rollback_run_id, property_id, variant, channel)
);
CREATE TABLE IF NOT EXISTS certification.production_evidence_bundles (
  evidence_bundle_id uuid PRIMARY KEY,
  production_certification_id uuid NOT NULL REFERENCES certification.production_runs(production_certification_id),
  candidate_fingerprint char(64) NOT NULL,
  required_codes jsonb NOT NULL,
  status text NOT NULL CHECK (status = 'PASS'),
  bundle_fingerprint char(64) NOT NULL UNIQUE,
  built_by text NOT NULL,
  built_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS certification.production_evidence_bundle_items (
  evidence_bundle_id uuid NOT NULL REFERENCES certification.production_evidence_bundles(evidence_bundle_id),
  evidence_code text NOT NULL,
  evidence_fingerprint char(64) NOT NULL,
  status text NOT NULL CHECK (status IN ('PASS','FAIL','BLOCKED')),
  PRIMARY KEY (evidence_bundle_id, evidence_code)
);
CREATE TABLE IF NOT EXISTS certification.production_certification_revocations (
  revocation_id uuid PRIMARY KEY,
  production_certification_id uuid NOT NULL REFERENCES certification.production_runs(production_certification_id),
  candidate_fingerprint char(64) NOT NULL,
  evidence_bundle_id uuid NOT NULL REFERENCES certification.production_evidence_bundles(evidence_bundle_id),
  evidence_bundle_fingerprint char(64) NOT NULL,
  reason_code text NOT NULL,
  detail text NOT NULL,
  revoked_by text NOT NULL,
  revocation_fingerprint char(64) NOT NULL UNIQUE,
  revoked_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS certification.full_approvals (
  full_approval_id uuid PRIMARY KEY,
  production_certification_id uuid NOT NULL REFERENCES certification.production_runs(production_certification_id),
  policy_version text NOT NULL,
  candidate_fingerprint char(64) NOT NULL,
  evidence_bundle_id uuid NOT NULL REFERENCES certification.production_evidence_bundles(evidence_bundle_id),
  evidence_bundle_fingerprint char(64) NOT NULL,
  stop_condition_fingerprint char(64) NOT NULL,
  rollout_stage_certification_fingerprints jsonb NOT NULL,
  approval_fingerprint char(64) NOT NULL UNIQUE,
  approved_by text NOT NULL,
  approved_at timestamptz NOT NULL DEFAULT now(),
  approval_type text NOT NULL DEFAULT 'FULL_APPROVAL' CHECK (approval_type = 'FULL_APPROVAL'),
  UNIQUE (production_certification_id, candidate_fingerprint)
);

DO $$ BEGIN
  CREATE TRIGGER trg_rollback_containment_runs_immutable BEFORE UPDATE OR DELETE ON certification.rollback_containment_runs FOR EACH ROW EXECUTE FUNCTION shared.raise_immutable_row();
EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN
  CREATE TRIGGER trg_rollback_containment_items_immutable BEFORE UPDATE OR DELETE ON certification.rollback_containment_items FOR EACH ROW EXECUTE FUNCTION shared.raise_immutable_row();
EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN
  CREATE TRIGGER trg_production_evidence_bundles_immutable BEFORE UPDATE OR DELETE ON certification.production_evidence_bundles FOR EACH ROW EXECUTE FUNCTION shared.raise_immutable_row();
EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN
  CREATE TRIGGER trg_production_evidence_bundle_items_immutable BEFORE UPDATE OR DELETE ON certification.production_evidence_bundle_items FOR EACH ROW EXECUTE FUNCTION shared.raise_immutable_row();
EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN
  CREATE TRIGGER trg_production_certification_revocations_immutable BEFORE UPDATE OR DELETE ON certification.production_certification_revocations FOR EACH ROW EXECUTE FUNCTION shared.raise_immutable_row();
EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN
  CREATE TRIGGER trg_full_approvals_immutable BEFORE UPDATE OR DELETE ON certification.full_approvals FOR EACH ROW EXECUTE FUNCTION shared.raise_immutable_row();
EXCEPTION WHEN duplicate_object THEN NULL; END $$;
