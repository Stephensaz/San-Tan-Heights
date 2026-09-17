-- STH M3-004: additive reference seed for regeneration event taxonomy.
BEGIN;
INSERT INTO reference.event_type (code) VALUES ('REGENERATION_JOB_QUEUED') ON CONFLICT (code) DO NOTHING;
COMMIT;
