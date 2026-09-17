-- STH M7-005 through M7-006: production configuration validation and frozen pilot membership evidence.
-- Shadow cycle persistence is intentionally deferred to M7-008.
BEGIN;

CREATE TABLE IF NOT EXISTS certification.production_configuration_validations (
  production_certification_id uuid PRIMARY KEY REFERENCES certification.production_runs(production_certification_id),
  policy_version text NOT NULL CHECK (length(btrim(policy_version)) > 0),
  configuration_fingerprint char(64) NOT NULL CHECK (configuration_fingerprint ~ '^[0-9a-f]{64}$'),
  validation_status text NOT NULL CHECK (validation_status IN ('PASS','FAIL','BLOCKED')),
  violation_codes jsonb NOT NULL DEFAULT '[]'::jsonb,
  observed_configuration jsonb NOT NULL,
  validator_version text NOT NULL CHECK (length(btrim(validator_version)) > 0),
  validated_by text NOT NULL CHECK (length(btrim(validated_by)) > 0),
  validated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS certification.production_pilot_memberships (
  production_certification_id uuid PRIMARY KEY REFERENCES certification.production_runs(production_certification_id),
  policy_version text NOT NULL CHECK (length(btrim(policy_version)) > 0),
  membership_fingerprint char(64) NOT NULL CHECK (membership_fingerprint ~ '^[0-9a-f]{64}$'),
  selected_count integer NOT NULL CHECK (selected_count >= 0),
  selected_property_ids jsonb NOT NULL,
  decision_evidence jsonb NOT NULL,
  resolved_by text NOT NULL CHECK (length(btrim(resolved_by)) > 0),
  resolved_at timestamptz NOT NULL DEFAULT now()
);

CREATE OR REPLACE FUNCTION certification.prevent_production_readiness_evidence_mutation()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'production readiness evidence is immutable';
END $$;

DROP TRIGGER IF EXISTS trg_production_configuration_validation_immutable ON certification.production_configuration_validations;
CREATE TRIGGER trg_production_configuration_validation_immutable
  BEFORE UPDATE OR DELETE ON certification.production_configuration_validations
  FOR EACH ROW EXECUTE FUNCTION certification.prevent_production_readiness_evidence_mutation();

DROP TRIGGER IF EXISTS trg_production_pilot_membership_immutable ON certification.production_pilot_memberships;
CREATE TRIGGER trg_production_pilot_membership_immutable
  BEFORE UPDATE OR DELETE ON certification.production_pilot_memberships
  FOR EACH ROW EXECUTE FUNCTION certification.prevent_production_readiness_evidence_mutation();

COMMIT;
