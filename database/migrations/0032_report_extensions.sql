-- STH M3-008: integrity constraints for report state.
BEGIN;
ALTER TABLE reporting.report_versions
    DROP CONSTRAINT IF EXISTS chk_ready_report_qa;
ALTER TABLE reporting.report_versions
    ADD CONSTRAINT chk_ready_report_qa CHECK (
      content_state <> 'READY' OR (qa_status='PASS' AND qa_completed_at IS NOT NULL)
    );
COMMIT;
