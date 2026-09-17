from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_gitignore_excludes_generated_certification_evidence_and_python_noise():
    text = (ROOT / '.gitignore').read_text(encoding='utf-8')
    assert 'artifacts/certification/' in text
    assert '__pycache__/' in text
    assert '.pytest_cache/' in text


def test_bootstrap_script_refuses_force_push_and_requires_clean_tree():
    text = (ROOT / 'scripts/certification/bootstrap_github_remote.py').read_text(encoding='utf-8')
    assert "status', '--porcelain'" in text
    assert "'push', '--set-upstream'" in text
    assert "'--force'" not in text
    assert "'push', '-f'" not in text
    assert 'remote must be a github.com HTTPS or SSH repository URL' in text
