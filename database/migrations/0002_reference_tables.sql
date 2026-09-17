-- STH M1-005: Reference-table foundation. No PostgreSQL native ENUM types.
BEGIN;

CREATE TABLE IF NOT EXISTS reference.content_state (
    code text PRIMARY KEY,
    description text NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS reference.publication_state (
    code text PRIMARY KEY,
    description text NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS reference.health_state (
    code text PRIMARY KEY,
    description text NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS reference.job_state (
    code text PRIMARY KEY,
    description text NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS reference.release_state (
    code text PRIMARY KEY,
    description text NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS reference.qa_status (
    code text PRIMARY KEY,
    description text NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS reference.render_type (
    code text PRIMARY KEY,
    description text NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS reference.report_variant (
    code text PRIMARY KEY,
    description text NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS reference.reason_code (
    code text PRIMARY KEY,
    description text NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS reference.error_code (
    code text PRIMARY KEY,
    description text NOT NULL DEFAULT ''
);

COMMIT;
