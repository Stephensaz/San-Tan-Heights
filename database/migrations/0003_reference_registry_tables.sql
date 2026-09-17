-- STH M1-006: Additional registry-backed reference tables. Additive migration; M1-005 migrations remain immutable.
BEGIN;

CREATE TABLE IF NOT EXISTS reference.event_type (
    code text PRIMARY KEY,
    version integer NOT NULL CHECK (version > 0),
    description text NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS reference.guard_id (
    code text PRIMARY KEY,
    description text NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS reference.data_classification (
    code text PRIMARY KEY,
    description text NOT NULL DEFAULT ''
);

COMMIT;
