from pathlib import Path
SQL=(Path(__file__).resolve().parents[3]/'database/migrations/0088_production_candidate_manifest_environment.sql').read_text()

def test_candidate_manifest_environment_tables_exist():
    for token in ['certification.production_candidate_freezes','certification.production_manifest_pins','certification.production_environment_parity']:
        assert token in SQL


def test_freeze_evidence_is_immutable():
    assert 'BEFORE UPDATE OR DELETE ON certification.production_candidate_freezes' in SQL
    assert 'BEFORE UPDATE OR DELETE ON certification.production_manifest_pins' in SQL
    assert 'BEFORE UPDATE OR DELETE ON certification.production_environment_parity' in SQL


def test_environment_parity_is_fail_closed_shape():
    assert "parity_status IN ('PASS','FAIL','BLOCKED')" in SQL
    assert 'mismatch_keys jsonb NOT NULL' in SQL
