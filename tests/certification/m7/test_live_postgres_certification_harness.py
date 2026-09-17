import json
import subprocess
from hashlib import sha256
from pathlib import Path

import pytest

from src.production_certification.certification import load_live_postgresql_evidence
from src.shared.canonical_json import canonical_json

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / 'scripts/certification/run_live_postgres_certification.py'
MIGRATION = ROOT / 'database/migrations/0143_least_privilege_completion.sql'


def _hash(payload):
    return sha256(canonical_json(payload).encode('utf-8')).hexdigest()


def test_live_postgres_harness_exists_and_exposes_help():
    cp = subprocess.run(['python', str(SCRIPT), '--help'], text=True, capture_output=True)
    assert cp.returncode == 0
    assert 'PostgreSQL 16+' in cp.stdout
    assert '--evidence-out' in cp.stdout
    assert '--candidate-fingerprint' in cp.stdout
    assert '--source-revision' in cp.stdout


def test_live_postgres_evidence_loader_verifies_fingerprint(tmp_path):
    payload = {
        'schema_version': '1.1.0',
        'candidate_fingerprint': 'c' * 64,
        'source_revision': 'deadbeef',
        'available': True,
        'executed': True,
        'check_statuses': {
            'MIGRATIONS_EXECUTED': 'PASS',
            'IMMUTABILITY_TRIGGERS_VERIFIED': 'PASS',
            'LEAST_PRIVILEGE_GRANTS_VERIFIED': 'PASS',
            'LOCKING_AND_CONCURRENCY_VERIFIED': 'PASS',
            'BACKUP_RESTORE_VERIFIED': 'PASS',
        },
        'detail': {'fixture': True},
    }
    payload['evidence_fingerprint'] = _hash(payload)
    path = tmp_path / 'evidence.json'
    path.write_text(json.dumps(payload))
    evidence = load_live_postgresql_evidence(path)
    assert evidence.available is True
    assert evidence.executed is True
    assert set(evidence.check_statuses.values()) == {'PASS'}
    assert evidence.candidate_fingerprint == 'c' * 64
    assert evidence.source_revision == 'deadbeef'


def test_live_postgres_evidence_loader_rejects_tampering(tmp_path):
    payload = {
        'schema_version': '1.1.0',
        'candidate_fingerprint': 'c' * 64,
        'source_revision': 'deadbeef',
        'available': True,
        'executed': True,
        'check_statuses': {'MIGRATIONS_EXECUTED': 'PASS'},
        'detail': {},
    }
    payload['evidence_fingerprint'] = _hash(payload)
    payload['executed'] = False
    path = tmp_path / 'evidence.json'
    path.write_text(json.dumps(payload))
    with pytest.raises(ValueError, match='fingerprint mismatch'):
        load_live_postgresql_evidence(path)


def test_public_projection_migration_uses_canonical_version_column():
    sql = MIGRATION.read_text()
    assert 'r.version_number AS report_version' in sql
    assert 'r.report_version' not in sql
