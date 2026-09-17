from pathlib import Path

def test_go_live_tables_and_immutability_are_present():
    sql=Path('database/migrations/0091_shadow_acceptance_stop_limited_approval.sql').read_text()
    for table in ('production_shadow_acceptance','production_go_live_stop_results','production_limited_approvals'):
        assert f'CREATE TABLE IF NOT EXISTS certification.{table}' in sql
    assert "approval_type='LIMITED'" in sql
    assert 'prevent_go_live_evidence_mutation' in sql
    assert 'BEFORE UPDATE OR DELETE' in sql
