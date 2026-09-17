CREATE TABLE IF NOT EXISTS orchestration.report_impact_evaluations (
  impact_evaluation_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  source_event_id uuid NOT NULL REFERENCES audit.orchestration_events(event_id),
  batch_id uuid NULL,
  property_id uuid NOT NULL REFERENCES core.properties(property_id),
  report_id uuid NULL,
  report_variant text NOT NULL REFERENCES reference.report_variant(code),
  dependency_type text NOT NULL,
  dependency_id text NOT NULL,
  stored_fingerprint text NOT NULL,
  current_fingerprint text NULL,
  change_class text NOT NULL,
  decision text NOT NULL CHECK (decision IN ('NO_IMPACT','DIRTY','BLOCKED','INVALIDATION_REQUIRED','REVIEW_REQUIRED')),
  impact_rule_id text NOT NULL,
  impact_rule_version text NOT NULL,
  reason_code text NOT NULL REFERENCES reference.reason_code(code),
  evaluated_at timestamptz NOT NULL DEFAULT now(),
  correlation_id uuid NOT NULL,
  UNIQUE(source_event_id,property_id,report_variant,dependency_type,dependency_id)
);
CREATE INDEX IF NOT EXISTS idx_impact_eval_dependency ON orchestration.report_impact_evaluations(dependency_type,dependency_id);
CREATE INDEX IF NOT EXISTS idx_impact_eval_property ON orchestration.report_impact_evaluations(property_id,report_variant,evaluated_at DESC);
CREATE INDEX IF NOT EXISTS idx_snapshot_dependency_reverse_lookup ON snapshot.snapshot_dependencies(dependency_type,dependency_id,snapshot_id);
