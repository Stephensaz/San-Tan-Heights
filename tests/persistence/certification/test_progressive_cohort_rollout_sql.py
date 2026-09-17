from pathlib import Path


def test_progressive_rollout_tables_are_append_only_and_cover_all_expansion_stages():
    sql = Path('database/migrations/0093_progressive_cohort_rollout.sql').read_text()
    for table in (
        'production_progressive_cohorts', 'production_progressive_cohort_members',
        'production_progressive_cohort_deployments', 'production_progressive_cohort_deployment_items',
        'production_progressive_cohort_certifications',
    ):
        assert f'CREATE TABLE IF NOT EXISTS certification.{table}' in sql
    assert "COHORT_100','COHORT_500','REMAINING_FLEET" in sql
    assert 'prior_cohort_certification_fingerprint' in sql
    assert 'fleet_eligibility_fingerprint' in sql
    assert 'prevent_progressive_rollout_evidence_mutation' in sql
    assert sql.count('BEFORE UPDATE OR DELETE') >= 5
