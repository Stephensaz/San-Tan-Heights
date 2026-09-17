-- STH M7-008 through M7-010: shadow-cycle tracking and manual-audit evidence.
BEGIN;

CREATE TABLE IF NOT EXISTS certification.production_shadow_cycles (
  shadow_cycle_id uuid PRIMARY KEY,
  production_certification_id uuid NOT NULL REFERENCES certification.production_runs(production_certification_id),
  cycle_number integer NOT NULL CHECK (cycle_number >= 1),
  policy_version text NOT NULL CHECK (length(btrim(policy_version)) > 0),
  pilot_membership_fingerprint char(64) NOT NULL CHECK (pilot_membership_fingerprint ~ '^[0-9a-f]{64}$'),
  target_count integer NOT NULL CHECK (target_count >= 0),
  passed_target_count integer NOT NULL CHECK (passed_target_count >= 0),
  failed_target_count integer NOT NULL CHECK (failed_target_count >= 0),
  cycle_status text NOT NULL CHECK (cycle_status IN ('PASS','FAIL')),
  orchestrator_evidence_hash char(64) NOT NULL CHECK (orchestrator_evidence_hash ~ '^[0-9a-f]{64}$'),
  cycle_fingerprint char(64) NOT NULL CHECK (cycle_fingerprint ~ '^[0-9a-f]{64}$'),
  recorded_by text NOT NULL CHECK (length(btrim(recorded_by)) > 0),
  recorded_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (production_certification_id, cycle_number),
  UNIQUE (production_certification_id, cycle_fingerprint),
  CHECK (passed_target_count + failed_target_count = target_count)
);

CREATE TABLE IF NOT EXISTS certification.production_shadow_cycle_targets (
  shadow_cycle_id uuid NOT NULL REFERENCES certification.production_shadow_cycles(shadow_cycle_id),
  property_id uuid NOT NULL REFERENCES core.properties(property_id),
  report_variant text NOT NULL CHECK (report_variant IN ('AGENT','SELLER','PUBLIC')),
  target_status text NOT NULL CHECK (target_status IN ('PASS','FAIL')),
  generated_fingerprint char(64) NULL CHECK (generated_fingerprint IS NULL OR generated_fingerprint ~ '^[0-9a-f]{64}$'),
  comparison_fingerprint char(64) NULL CHECK (comparison_fingerprint IS NULL OR comparison_fingerprint ~ '^[0-9a-f]{64}$'),
  detail jsonb NOT NULL DEFAULT '{}'::jsonb,
  target_evidence_hash char(64) NOT NULL CHECK (target_evidence_hash ~ '^[0-9a-f]{64}$'),
  PRIMARY KEY (shadow_cycle_id, property_id, report_variant)
);

CREATE TABLE IF NOT EXISTS certification.production_manual_audit_samples (
  manual_audit_sample_id uuid PRIMARY KEY,
  production_certification_id uuid NOT NULL REFERENCES certification.production_runs(production_certification_id),
  shadow_cycle_id uuid NOT NULL REFERENCES certification.production_shadow_cycles(shadow_cycle_id),
  policy_version text NOT NULL CHECK (length(btrim(policy_version)) > 0),
  sample_size integer NOT NULL CHECK (sample_size >= 1),
  sampled_property_ids jsonb NOT NULL,
  failed_shadow_property_ids jsonb NOT NULL DEFAULT '[]'::jsonb,
  sample_fingerprint char(64) NOT NULL CHECK (sample_fingerprint ~ '^[0-9a-f]{64}$'),
  built_by text NOT NULL CHECK (length(btrim(built_by)) > 0),
  built_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (production_certification_id, shadow_cycle_id, policy_version)
);

CREATE TABLE IF NOT EXISTS certification.production_manual_audit_evidence (
  manual_audit_evidence_id uuid PRIMARY KEY,
  manual_audit_sample_id uuid NOT NULL REFERENCES certification.production_manual_audit_samples(manual_audit_sample_id),
  property_id uuid NOT NULL REFERENCES core.properties(property_id),
  audit_status text NOT NULL CHECK (audit_status IN ('PASS','FAIL','REVIEW_REQUIRED')),
  checklist_version text NOT NULL CHECK (length(btrim(checklist_version)) > 0),
  checklist_results jsonb NOT NULL,
  notes text NULL,
  evidence_hash char(64) NOT NULL CHECK (evidence_hash ~ '^[0-9a-f]{64}$'),
  reviewed_by text NOT NULL CHECK (length(btrim(reviewed_by)) > 0),
  reviewed_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (manual_audit_sample_id, property_id)
);

CREATE OR REPLACE FUNCTION certification.prevent_shadow_audit_evidence_mutation()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'shadow/manual-audit certification evidence is immutable';
END $$;

DROP TRIGGER IF EXISTS trg_production_shadow_cycles_immutable ON certification.production_shadow_cycles;
CREATE TRIGGER trg_production_shadow_cycles_immutable
  BEFORE UPDATE OR DELETE ON certification.production_shadow_cycles
  FOR EACH ROW EXECUTE FUNCTION certification.prevent_shadow_audit_evidence_mutation();

DROP TRIGGER IF EXISTS trg_production_shadow_cycle_targets_immutable ON certification.production_shadow_cycle_targets;
CREATE TRIGGER trg_production_shadow_cycle_targets_immutable
  BEFORE UPDATE OR DELETE ON certification.production_shadow_cycle_targets
  FOR EACH ROW EXECUTE FUNCTION certification.prevent_shadow_audit_evidence_mutation();

DROP TRIGGER IF EXISTS trg_production_manual_audit_samples_immutable ON certification.production_manual_audit_samples;
CREATE TRIGGER trg_production_manual_audit_samples_immutable
  BEFORE UPDATE OR DELETE ON certification.production_manual_audit_samples
  FOR EACH ROW EXECUTE FUNCTION certification.prevent_shadow_audit_evidence_mutation();

DROP TRIGGER IF EXISTS trg_production_manual_audit_evidence_immutable ON certification.production_manual_audit_evidence;
CREATE TRIGGER trg_production_manual_audit_evidence_immutable
  BEFORE UPDATE OR DELETE ON certification.production_manual_audit_evidence
  FOR EACH ROW EXECUTE FUNCTION certification.prevent_shadow_audit_evidence_mutation();

COMMIT;
