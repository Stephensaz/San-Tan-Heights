-- STH M1-007: Audit tables are append-only.
BEGIN;
DROP TRIGGER IF EXISTS trg_orchestration_events_immutable ON audit.orchestration_events;
CREATE TRIGGER trg_orchestration_events_immutable BEFORE UPDATE OR DELETE ON audit.orchestration_events FOR EACH ROW EXECUTE FUNCTION audit.prevent_immutable_mutation();
DROP TRIGGER IF EXISTS trg_state_transitions_immutable ON audit.state_transitions;
CREATE TRIGGER trg_state_transitions_immutable BEFORE UPDATE OR DELETE ON audit.state_transitions FOR EACH ROW EXECUTE FUNCTION audit.prevent_immutable_mutation();
DROP TRIGGER IF EXISTS trg_guard_evaluations_immutable ON audit.guard_evaluations;
CREATE TRIGGER trg_guard_evaluations_immutable BEFORE UPDATE OR DELETE ON audit.guard_evaluations FOR EACH ROW EXECUTE FUNCTION audit.prevent_immutable_mutation();
COMMIT;
