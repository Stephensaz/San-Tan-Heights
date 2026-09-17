-- STH M7-002 through M7-004: frozen candidate, manifest pins, and environment parity evidence.
BEGIN;

CREATE TABLE IF NOT EXISTS certification.production_candidate_freezes (
  production_certification_id uuid PRIMARY KEY REFERENCES certification.production_runs(production_certification_id),
  candidate_version text NOT NULL,
  candidate_fingerprint char(64) NOT NULL CHECK (candidate_fingerprint ~ '^[0-9a-f]{64}$'),
  artifact_sha256 char(64) NOT NULL CHECK (artifact_sha256 ~ '^[0-9a-f]{64}$'),
  source_revision text NOT NULL CHECK (length(btrim(source_revision)) > 0),
  artifact_uri text NOT NULL CHECK (length(btrim(artifact_uri)) > 0),
  freeze_fingerprint char(64) NOT NULL CHECK (freeze_fingerprint ~ '^[0-9a-f]{64}$'),
  frozen_by text NOT NULL CHECK (length(btrim(frozen_by)) > 0),
  frozen_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS certification.production_manifest_pins (
  production_certification_id uuid NOT NULL REFERENCES certification.production_runs(production_certification_id),
  manifest_type text NOT NULL CHECK (manifest_type IN ('CONTRACT_MANIFEST','BUILD_MANIFEST')),
  manifest_version text NOT NULL CHECK (length(btrim(manifest_version)) > 0),
  manifest_sha256 char(64) NOT NULL CHECK (manifest_sha256 ~ '^[0-9a-f]{64}$'),
  manifest_payload jsonb NOT NULL,
  pin_fingerprint char(64) NOT NULL CHECK (pin_fingerprint ~ '^[0-9a-f]{64}$'),
  pinned_by text NOT NULL CHECK (length(btrim(pinned_by)) > 0),
  pinned_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (production_certification_id, manifest_type)
);

CREATE TABLE IF NOT EXISTS certification.production_environment_parity (
  production_certification_id uuid PRIMARY KEY REFERENCES certification.production_runs(production_certification_id),
  policy_version text NOT NULL,
  expected_fingerprint char(64) NOT NULL CHECK (expected_fingerprint ~ '^[0-9a-f]{64}$'),
  observed_fingerprint char(64) NOT NULL CHECK (observed_fingerprint ~ '^[0-9a-f]{64}$'),
  parity_status text NOT NULL CHECK (parity_status IN ('PASS','FAIL','BLOCKED')),
  mismatch_keys jsonb NOT NULL DEFAULT '[]'::jsonb,
  expected_environment jsonb NOT NULL,
  observed_environment jsonb NOT NULL,
  verifier_version text NOT NULL,
  verified_by text NOT NULL,
  verified_at timestamptz NOT NULL DEFAULT now()
);

CREATE OR REPLACE FUNCTION certification.prevent_production_freeze_mutation()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'production certification freeze evidence is immutable';
END $$;

DROP TRIGGER IF EXISTS trg_production_candidate_freeze_immutable ON certification.production_candidate_freezes;
CREATE TRIGGER trg_production_candidate_freeze_immutable
  BEFORE UPDATE OR DELETE ON certification.production_candidate_freezes
  FOR EACH ROW EXECUTE FUNCTION certification.prevent_production_freeze_mutation();

DROP TRIGGER IF EXISTS trg_production_manifest_pins_immutable ON certification.production_manifest_pins;
CREATE TRIGGER trg_production_manifest_pins_immutable
  BEFORE UPDATE OR DELETE ON certification.production_manifest_pins
  FOR EACH ROW EXECUTE FUNCTION certification.prevent_production_freeze_mutation();

DROP TRIGGER IF EXISTS trg_production_environment_parity_immutable ON certification.production_environment_parity;
CREATE TRIGGER trg_production_environment_parity_immutable
  BEFORE UPDATE OR DELETE ON certification.production_environment_parity
  FOR EACH ROW EXECUTE FUNCTION certification.prevent_production_freeze_mutation();

COMMIT;
