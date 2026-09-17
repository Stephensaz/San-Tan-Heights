from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / 'scripts/certification/freeze_repository_candidate.py'


def _run(cmd, cwd):
    return subprocess.run(cmd, cwd=cwd, text=True, capture_output=True, check=True)


def test_candidate_freeze_script_requires_git_checkout():
    text = SCRIPT.read_text()
    assert "git_value('rev-parse', 'HEAD')" in text
    assert "git_value('rev-parse', 'HEAD^{tree}')" in text
    assert 'candidate freeze requires a clean committed checkout' in text
    assert 'CONTRACT-MANIFEST.yaml' in text
    assert 'BUILD-MANIFEST.yaml' in text
    assert 'ARCHITECTURE-LOCK.yaml' in text


def test_candidate_binding_is_deterministic_for_same_commit(tmp_path):
    repo = tmp_path / 'repo'
    repo.mkdir()
    (repo / 'scripts/certification').mkdir(parents=True)
    shutil.copy2(SCRIPT, repo / 'scripts/certification/freeze_repository_candidate.py')
    (repo / 'contracts/certification').mkdir(parents=True)
    (repo / 'VERSION').write_text('9.9.9\n')
    (repo / 'CONTRACT-MANIFEST.yaml').write_text('contract: v1\n')
    (repo / 'BUILD-MANIFEST.yaml').write_text('build: v1\n')
    (repo / 'ARCHITECTURE-LOCK.yaml').write_text('lock: v1\n')
    (repo / 'contracts/certification/STH-PRODUCTION-CERTIFICATION-v1.0.yaml').write_text('cert: v1\n')
    _run(['git', 'init'], repo)
    _run(['git', 'config', 'user.email', 'cert@example.invalid'], repo)
    _run(['git', 'config', 'user.name', 'Certification Test'], repo)
    _run(['git', 'add', '.'], repo)
    _run(['git', 'commit', '-m', 'candidate'], repo)

    out1 = repo / 'artifacts/certification/a.json'
    out2 = repo / 'artifacts/certification/b.json'
    _run(['python', str(repo / 'scripts/certification/freeze_repository_candidate.py'), '--out', str(out1)], repo)
    _run(['python', str(repo / 'scripts/certification/freeze_repository_candidate.py'), '--out', str(out2)], repo)
    a = json.loads(out1.read_text())
    b = json.loads(out2.read_text())
    assert a == b
    payload = {k: a[k] for k in ('schema_version','candidate_version','source_revision','source_tree','input_hashes')}
    expected = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()
    assert a['candidate_fingerprint'] == expected


def test_candidate_freeze_rejects_dirty_checkout(tmp_path):
    repo = tmp_path / 'repo'
    repo.mkdir()
    (repo / 'scripts/certification').mkdir(parents=True)
    shutil.copy2(SCRIPT, repo / 'scripts/certification/freeze_repository_candidate.py')
    (repo / 'contracts/certification').mkdir(parents=True)
    for path, value in {
        'VERSION': '1\n', 'CONTRACT-MANIFEST.yaml': 'a\n', 'BUILD-MANIFEST.yaml': 'b\n',
        'ARCHITECTURE-LOCK.yaml': 'c\n', 'contracts/certification/STH-PRODUCTION-CERTIFICATION-v1.0.yaml': 'd\n'
    }.items():
        p = repo / path; p.parent.mkdir(parents=True, exist_ok=True); p.write_text(value)
    _run(['git', 'init'], repo); _run(['git', 'config', 'user.email', 'x@y.invalid'], repo); _run(['git', 'config', 'user.name', 'T'], repo)
    _run(['git', 'add', '.'], repo); _run(['git', 'commit', '-m', 'candidate'], repo)
    (repo / 'VERSION').write_text('2\n')
    cp = subprocess.run(['python', str(repo / 'scripts/certification/freeze_repository_candidate.py')], cwd=repo, text=True, capture_output=True)
    assert cp.returncode != 0
    assert 'clean committed checkout' in (cp.stderr + cp.stdout)
