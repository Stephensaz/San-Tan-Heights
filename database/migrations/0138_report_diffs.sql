-- STH M7-027 remediation: create report diffs before least-privilege grants consume it.
BEGIN;
CREATE TABLE IF NOT EXISTS reporting.report_diffs (
    report_diff_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    old_report_id uuid NOT NULL REFERENCES reporting.report_versions(report_id),
    new_report_id uuid NOT NULL REFERENCES reporting.report_versions(report_id),
    diff_payload jsonb NOT NULL,
    diff_hash char(64) NOT NULL CHECK (diff_hash ~ '^[0-9a-f]{64}$'),
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE(old_report_id, new_report_id)
);
COMMIT;
