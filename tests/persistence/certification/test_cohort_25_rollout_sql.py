from pathlib import Path


def test_cohort_rollout_tables_and_immutability_are_present():
    sql=Path('database/migrations/0092_cohort_25_rollout.sql').read_text()
    for table in ('production_cohorts','production_cohort_members','production_cohort_deployments','production_cohort_deployment_items','production_cohort_certifications'):
        assert f'CREATE TABLE IF NOT EXISTS certification.{table}' in sql
    assert 'prevent_cohort_rollout_evidence_mutation' in sql
    assert sql.count('BEFORE UPDATE OR DELETE') >= 5
    assert 'UNIQUE (production_certification_id, cohort_code)' in sql
