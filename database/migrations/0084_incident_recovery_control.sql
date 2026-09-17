-- STH M5-023..M5-026: incident, containment, and explicit recovery command persistence.
BEGIN;
CREATE TABLE IF NOT EXISTS operations.incidents (
  incident_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  incident_key text NOT NULL UNIQUE,
  incident_type text NOT NULL,
  severity text NOT NULL CHECK (severity IN ('INFO','WARNING','ERROR','CRITICAL')),
  incident_state text NOT NULL CHECK (incident_state IN ('OPEN','CONTAINED','RECOVERING','RESOLVED','CLOSED')),
  source_rule_id text NULL,
  source_entity_type text NULL,
  source_entity_id text NULL,
  property_id uuid NULL REFERENCES core.properties(property_id),
  report_variant text NULL,
  channel text NULL,
  release_id uuid NULL REFERENCES operations.releases(release_id),
  reason_code text NOT NULL REFERENCES reference.reason_code(code),
  correlation_id uuid NULL,
  detected_at timestamptz NOT NULL DEFAULT now(),
  contained_at timestamptz NULL,
  resolved_at timestamptz NULL,
  closed_at timestamptz NULL,
  updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_incidents_active ON operations.incidents(severity,detected_at DESC)
WHERE incident_state IN ('OPEN','CONTAINED','RECOVERING');
CREATE INDEX IF NOT EXISTS idx_incidents_property ON operations.incidents(property_id,incident_state,detected_at DESC);
CREATE INDEX IF NOT EXISTS idx_incidents_release ON operations.incidents(release_id,incident_state,detected_at DESC);

CREATE TABLE IF NOT EXISTS operations.incident_history (
  history_id bigserial PRIMARY KEY,
  incident_id uuid NOT NULL REFERENCES operations.incidents(incident_id),
  from_state text NULL,
  to_state text NOT NULL,
  reason_code text NOT NULL REFERENCES reference.reason_code(code),
  actor text NOT NULL,
  correlation_id uuid NULL,
  occurred_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_incident_history_incident ON operations.incident_history(incident_id,history_id);

CREATE TABLE IF NOT EXISTS operations.containment_actions (
  containment_action_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  incident_id uuid NOT NULL REFERENCES operations.incidents(incident_id),
  action_type text NOT NULL,
  target_key text NOT NULL,
  action_status text NOT NULL CHECK (action_status IN ('PLANNED','APPLIED','NO_OP','FAILED')),
  reason_code text NOT NULL REFERENCES reference.reason_code(code),
  evidence_json jsonb NOT NULL DEFAULT '{}'::jsonb,
  applied_by text NOT NULL,
  correlation_id uuid NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  applied_at timestamptz NULL,
  UNIQUE(incident_id,action_type,target_key)
);

CREATE TABLE IF NOT EXISTS operations.recovery_commands (
  recovery_command_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  incident_id uuid NOT NULL REFERENCES operations.incidents(incident_id),
  idempotency_key text NOT NULL,
  command_type text NOT NULL,
  request_hash char(64) NOT NULL CHECK (request_hash ~ '^[0-9a-f]{64}$'),
  command_status text NOT NULL CHECK (command_status IN ('REQUESTED','RUNNING','SUCCEEDED','FAILED','BLOCKED','NO_OP')),
  command_payload jsonb NOT NULL DEFAULT '{}'::jsonb,
  result_json jsonb NULL,
  reason_code text NOT NULL REFERENCES reference.reason_code(code),
  requested_by text NOT NULL,
  correlation_id uuid NULL,
  requested_at timestamptz NOT NULL DEFAULT now(),
  started_at timestamptz NULL,
  completed_at timestamptz NULL,
  UNIQUE(incident_id,idempotency_key)
);
CREATE INDEX IF NOT EXISTS idx_recovery_commands_incident ON operations.recovery_commands(incident_id,requested_at DESC);

CREATE TABLE IF NOT EXISTS operations.recovery_command_history (
  history_id bigserial PRIMARY KEY,
  recovery_command_id uuid NOT NULL REFERENCES operations.recovery_commands(recovery_command_id),
  from_status text NULL,
  to_status text NOT NULL,
  reason_code text NOT NULL REFERENCES reference.reason_code(code),
  actor text NOT NULL,
  detail_json jsonb NOT NULL DEFAULT '{}'::jsonb,
  occurred_at timestamptz NOT NULL DEFAULT now()
);
COMMIT;
