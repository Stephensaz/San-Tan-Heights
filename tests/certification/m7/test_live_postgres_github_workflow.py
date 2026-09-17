from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]
WORKFLOW = ROOT / '.github/workflows/m7-live-postgres-certification.yml'


def _workflow():
    return yaml.safe_load(WORKFLOW.read_text())


def test_m7_live_postgres_workflow_is_present_and_uses_postgres16():
    data = _workflow()
    assert data['name'] == 'M7 Live PostgreSQL Certification'
    job = data['jobs']['certify-postgresql-16']
    assert job['runs-on'] == 'ubuntu-24.04'
    assert job['services']['postgres']['image'] == 'postgres:16'
    assert job['permissions'] if 'permissions' in job else True


def test_m7_live_postgres_workflow_runs_harness_and_uploads_evidence():
    text = WORKFLOW.read_text()
    assert 'run_live_postgres_certification.py' in text
    assert 'load_live_postgresql_evidence' in text
    assert 'actions/upload-artifact@v4' in text
    assert 'live-postgres-evidence.json' in text
    assert 'MIGRATIONS_EXECUTED' in text
    assert 'IMMUTABILITY_TRIGGERS_VERIFIED' in text
    assert 'LEAST_PRIVILEGE_GRANTS_VERIFIED' in text
    assert 'LOCKING_AND_CONCURRENCY_VERIFIED' in text
    assert 'BACKUP_RESTORE_VERIFIED' in text
    assert 'freeze_repository_candidate.py' in text
    assert 'candidate-binding.json' in text
    assert 'expected_candidate_fingerprint' in text
    assert 'candidate_fingerprint' in text
    assert '--candidate-fingerprint' in text
    assert '--source-revision' in text


def test_m7_live_postgres_workflow_has_no_production_credentials():
    text = WORKFLOW.read_text().lower()
    assert 'production_password' not in text
    assert 'prod_password' not in text
    assert 'secrets.' not in text
    assert 'postgres-cert-only' in text
