-- STH M3-004: additive reference seed for regeneration event taxonomy.
BEGIN;
INSERT INTO reference.event_type (code, version) VALUES ('REGENERATION_JOB_QUEUED', 1)
ON CONFLICT (code) DO UPDATE SET version=EXCLUDED.version;
COMMIT;
