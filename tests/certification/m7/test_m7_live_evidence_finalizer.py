import json
from hashlib import sha256
from pathlib import Path

import yaml

from src.production_certification.certification import FinalCertificationPolicy, load_live_postgresql_evidence
from src.production_certification.certification.finalizer import M7LiveEvidenceFinalizer
from src.shared.canonical_json import canonical_json

ROOT = Path(__file__).resolve().parents[3]
CAND = 'c' * 64
REV = 'deadbeef'


def _hash(payload):
    return sha256(canonical_json(payload).encode()).hexdigest()


def _evidence(tmp_path, *, candidate=CAND, revision=REV, status='PASS'):
    policy = FinalCertificationPolicy.load(ROOT / 'registries/production-certification/final-certification-policy.yaml')
    payload = {
        'schema_version': '1.1.0',
        'candidate_fingerprint': candidate,
        'source_revision': revision,
        'available': True,
        'executed': True,
        'check_statuses': {code: status for code in policy.required_live_postgresql_checks},
        'detail': {'fixture': True},
    }
    payload['evidence_fingerprint'] = _hash(payload)
    path = tmp_path / 'evidence.json'
    path.write_text(json.dumps(payload))
    return policy, path, load_live_postgresql_evidence(path)


def test_finalizer_assessment_requires_candidate_source_and_five_passes(tmp_path):
    policy, _, evidence = _evidence(tmp_path)
    result = M7LiveEvidenceFinalizer().assess(policy=policy, evidence=evidence, candidate_fingerprint=CAND, source_revision=REV)
    assert result.eligible is True
    assert result.status == 'READY_TO_ACCEPT'
    assert set(result.check_statuses.values()) == {'PASS'}


def test_finalizer_assessment_rejects_candidate_or_check_drift(tmp_path):
    policy, _, evidence = _evidence(tmp_path, status='FAIL')
    result = M7LiveEvidenceFinalizer().assess(policy=policy, evidence=evidence, candidate_fingerprint='d' * 64, source_revision=REV)
    assert result.eligible is False
    assert 'LIVE_POSTGRES_CANDIDATE_MISMATCH' in result.reason_codes
    assert any(code.endswith('_NOT_PASS') for code in result.reason_codes)


def test_finalizer_applies_only_expected_blocked_to_m8_transition(tmp_path):
    repo = tmp_path / 'repo'
    repo.mkdir()
    for rel in ('BUILD-MANIFEST.yaml','IMPLEMENTATION-BACKLOG.yaml','IMPLEMENTATION-BACKLOG.csv','VERSION','CHANGELOG.md','docs/implementation/M7-027.md'):
        src = ROOT / rel
        dst = repo / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(src.read_bytes())
    policy, path, evidence = _evidence(tmp_path)
    assessment = M7LiveEvidenceFinalizer().assess(policy=policy, evidence=evidence, candidate_fingerprint=CAND, source_revision=REV)
    before = (repo / 'VERSION').read_text().strip()
    major, minor, patch = (int(x) for x in before.split('.'))
    version = M7LiveEvidenceFinalizer().apply_repository_transition(repo_root=repo, evidence_path=path, assessment=assessment, test_count=999)
    assert version == f'{major}.{minor}.{patch + 1}'
    build = yaml.safe_load((repo / 'BUILD-MANIFEST.yaml').read_text())
    assert build['current_ticket'] == 'M8-001'
    assert next(x for x in build['milestones'] if x['id']=='M7')['status'] == 'ACCEPTED'
    assert next(x for x in build['milestones'] if x['id']=='M8')['status'] == 'IN_PROGRESS'
    backlog = yaml.safe_load((repo / 'IMPLEMENTATION-BACKLOG.yaml').read_text())
    tickets = {x['ticket_id']: x for x in backlog['tickets']}
    assert tickets['M7-027']['status'] == 'ACCEPTED'
    assert tickets['M8-001']['status'] == 'IN_PROGRESS'
    assert (repo / 'artifacts/certification/m7-027-live-postgres-evidence.json').exists()
