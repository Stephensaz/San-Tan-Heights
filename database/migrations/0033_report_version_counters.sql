-- STH M3-009: concurrency-safe report version allocation.
BEGIN;
CREATE TABLE IF NOT EXISTS reporting.report_version_counters (
    property_id uuid NOT NULL REFERENCES core.properties(property_id),
    report_variant text NOT NULL REFERENCES reference.report_variant(code),
    next_version bigint NOT NULL DEFAULT 1 CHECK (next_version > 0),
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY(property_id, report_variant)
);
COMMIT;
