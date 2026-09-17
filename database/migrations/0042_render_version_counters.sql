-- STH M4-002: concurrency-safe render version allocation per immutable report and render type.
BEGIN;
CREATE TABLE IF NOT EXISTS reporting.render_version_counters (
    report_id uuid NOT NULL REFERENCES reporting.report_versions(report_id),
    render_type text NOT NULL REFERENCES reference.render_type(code),
    next_version bigint NOT NULL DEFAULT 1 CHECK (next_version > 0),
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY(report_id, render_type)
);
COMMIT;
