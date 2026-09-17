-- STH M1-007: Audit query indexes.
BEGIN;
CREATE INDEX IF NOT EXISTS idx_orch_events_correlation ON audit.orchestration_events(correlation_id, recorded_at);
CREATE INDEX IF NOT EXISTS idx_orch_events_property ON audit.orchestration_events(property_id, recorded_at) WHERE property_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_orch_events_type ON audit.orchestration_events(event_type, recorded_at);
CREATE INDEX IF NOT EXISTS idx_state_transitions_entity ON audit.state_transitions(entity_type, entity_id, recorded_at);
CREATE INDEX IF NOT EXISTS idx_state_transitions_correlation ON audit.state_transitions(correlation_id, recorded_at);
CREATE INDEX IF NOT EXISTS idx_guard_evaluations_transition ON audit.guard_evaluations(transition_record_id, ordinal);
COMMIT;
