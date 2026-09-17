-- STH M1-014: Add reason codes used by the governed transition/guard runtime.
BEGIN;
INSERT INTO reference.reason_code (code) VALUES ('TRANSITION_CONFLICT') ON CONFLICT (code) DO NOTHING;
INSERT INTO reference.reason_code (code) VALUES ('GUARD_EXECUTION_ERROR') ON CONFLICT (code) DO NOTHING;
INSERT INTO reference.reason_code (code) VALUES ('PRIOR_GUARD_STOPPED') ON CONFLICT (code) DO NOTHING;
INSERT INTO reference.reason_code (code) VALUES ('ENTITY_NOT_FOUND') ON CONFLICT (code) DO NOTHING;
INSERT INTO reference.reason_code (code) VALUES ('EXPECTED_STATE_MISMATCH') ON CONFLICT (code) DO NOTHING;
COMMIT;
