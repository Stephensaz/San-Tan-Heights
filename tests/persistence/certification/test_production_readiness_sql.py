from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
SQL=(ROOT/'database/migrations/0089_production_configuration_and_pilot.sql').read_text()
def test_configuration_and_pilot_evidence_tables_are_immutable():
    assert 'certification.production_configuration_validations' in SQL
    assert 'certification.production_pilot_memberships' in SQL
    assert 'BEFORE UPDATE OR DELETE' in SQL
    assert 'production readiness evidence is immutable' in SQL
