from pathlib import Path
SQL=(Path(__file__).resolve().parents[3]/'database/migrations/0090_shadow_cycle_manual_audit.sql').read_text()

def test_shadow_and_manual_audit_tables_exist():
    for token in ['certification.production_shadow_cycles','certification.production_shadow_cycle_targets',
                  'certification.production_manual_audit_samples','certification.production_manual_audit_evidence']:
        assert token in SQL

def test_shadow_and_manual_audit_evidence_are_immutable():
    assert 'prevent_shadow_audit_evidence_mutation' in SQL
    for table in ['production_shadow_cycles','production_shadow_cycle_targets','production_manual_audit_samples','production_manual_audit_evidence']:
        assert f'BEFORE UPDATE OR DELETE ON certification.{table}' in SQL

def test_m7_008_010_do_not_define_shadow_acceptance_or_go_live_approval():
    assert 'FULL_APPROVAL' not in SQL
    assert 'LIMITED_APPROVAL' not in SQL
    assert 'shadow_acceptance' not in SQL.lower()
