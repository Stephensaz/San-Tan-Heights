from pathlib import Path

SQL = (Path(__file__).resolve().parents[3] / 'database/migrations/0087_production_certification_persistence.sql').read_text()


def test_production_certification_foundation_tables_exist():
    for token in [
        'certification.production_runs',
        'certification.production_evidence',
        'certification.production_check_results',
        'system_certification_run_id',
        'candidate_fingerprint',
    ]:
        assert token in SQL


def test_evidence_and_checks_are_append_only():
    assert 'prevent_production_evidence_mutation' in SQL
    assert 'BEFORE UPDATE OR DELETE ON certification.production_evidence' in SQL
    assert 'BEFORE UPDATE OR DELETE ON certification.production_check_results' in SQL


def test_m7_001_does_not_define_go_live_or_cohort_policy():
    # Persistence may store generic evidence/checks, but later tickets own operational semantics.
    assert 'FULL_APPROVAL' not in SQL
    assert 'LIMITED_APPROVAL' not in SQL
    assert 'cohort_size' not in SQL
    assert 'shadow_cycle' not in SQL
