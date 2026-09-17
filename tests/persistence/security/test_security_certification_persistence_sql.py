from pathlib import Path
SQL=(Path(__file__).resolve().parents[3]/'database/migrations/0086_security_audit_and_certification.sql').read_text()
def test_security_audit_and_certification_tables_append_only():
    for token in ['audit.security_events','certification.runs','certification.scenario_results','certification.metric_results','prevent_certification_evidence_mutation']:
        assert token in SQL
