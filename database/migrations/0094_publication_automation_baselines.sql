CREATE TABLE IF NOT EXISTS certification.automation_handoffs (
  automation_handoff_id uuid PRIMARY KEY,
  production_certification_id uuid NOT NULL REFERENCES certification.production_runs(production_certification_id),
  policy_version text NOT NULL,
  stage_code text NOT NULL,
  prior_stage text NOT NULL,
  candidate_fingerprint char(64) NOT NULL,
  prior_certification_id uuid NOT NULL,
  prior_certification_fingerprint char(64) NOT NULL,
  stop_condition_fingerprint char(64) NOT NULL,
  requested_by text NOT NULL,
  reason_code text NOT NULL,
  handoff_fingerprint char(64) NOT NULL UNIQUE,
  created_at timestamptz NOT NULL,
  UNIQUE (production_certification_id, stage_code)
);

CREATE TABLE IF NOT EXISTS certification.rollback_baselines (
  rollback_baseline_id uuid PRIMARY KEY,
  production_certification_id uuid NOT NULL REFERENCES certification.production_runs(production_certification_id),
  stage_code text NOT NULL,
  candidate_fingerprint char(64) NOT NULL,
  automation_handoff_id uuid NOT NULL REFERENCES certification.automation_handoffs(automation_handoff_id),
  automation_handoff_fingerprint char(64) NOT NULL,
  baseline_fingerprint char(64) NOT NULL UNIQUE,
  captured_by text NOT NULL,
  captured_at timestamptz NOT NULL,
  UNIQUE (production_certification_id, stage_code)
);

CREATE TABLE IF NOT EXISTS certification.rollback_baseline_entries (
  rollback_baseline_id uuid NOT NULL REFERENCES certification.rollback_baselines(rollback_baseline_id),
  property_id uuid NOT NULL REFERENCES core.properties(property_id),
  report_variant text NOT NULL,
  channel text NOT NULL,
  semantic_report_id uuid NULL REFERENCES reporting.report_versions(report_id),
  channel_render_id uuid NULL REFERENCES reporting.render_versions(render_id),
  entry_fingerprint char(64) NOT NULL,
  PRIMARY KEY (rollback_baseline_id, property_id, report_variant, channel),
  UNIQUE (rollback_baseline_id, entry_fingerprint)
);

DROP TRIGGER IF EXISTS trg_automation_handoffs_immutable ON certification.automation_handoffs;
CREATE TRIGGER trg_automation_handoffs_immutable BEFORE UPDATE OR DELETE ON certification.automation_handoffs
FOR EACH ROW EXECUTE FUNCTION shared.raise_immutable_row();
DROP TRIGGER IF EXISTS trg_rollback_baselines_immutable ON certification.rollback_baselines;
CREATE TRIGGER trg_rollback_baselines_immutable BEFORE UPDATE OR DELETE ON certification.rollback_baselines
FOR EACH ROW EXECUTE FUNCTION shared.raise_immutable_row();
DROP TRIGGER IF EXISTS trg_rollback_baseline_entries_immutable ON certification.rollback_baseline_entries;
CREATE TRIGGER trg_rollback_baseline_entries_immutable BEFORE UPDATE OR DELETE ON certification.rollback_baseline_entries
FOR EACH ROW EXECUTE FUNCTION shared.raise_immutable_row();
