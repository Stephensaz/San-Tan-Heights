#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git_value(*args: str) -> str:
    cp = subprocess.run(['git', *args], cwd=ROOT, text=True, capture_output=True)
    if cp.returncode != 0:
        raise SystemExit(
            'candidate freeze requires a committed Git checkout; '
            f"git {' '.join(args)} failed: {cp.stderr.strip() or cp.stdout.strip()}"
        )
    value = cp.stdout.strip()
    if not value:
        raise SystemExit(f"git {' '.join(args)} returned an empty value")
    return value


def canonical_hash(payload: dict) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode('utf-8')
    return hashlib.sha256(raw).hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser(description='Freeze the exact committed repository candidate for M7 live certification.')
    ap.add_argument('--out', default=str(ROOT / 'artifacts/certification/candidate-binding.json'))
    ap.add_argument('--expected-fingerprint', default=None)
    args = ap.parse_args()

    version = (ROOT / 'VERSION').read_text(encoding='utf-8').strip()
    if not version:
        raise SystemExit('VERSION is blank')

    source_revision = git_value('rev-parse', 'HEAD')
    source_tree = git_value('rev-parse', 'HEAD^{tree}')

    # A dirty checkout is not a frozen candidate. Untracked/generated certification artifacts
    # are ignored only when they live under artifacts/certification/.
    cp = subprocess.run(['git', 'status', '--porcelain'], cwd=ROOT, text=True, capture_output=True)
    if cp.returncode != 0:
        raise SystemExit(cp.stderr.strip() or 'git status failed')
    dirty = []
    for line in cp.stdout.splitlines():
        path = line[3:] if len(line) > 3 else ''
        if line.startswith('?? ') and path.startswith('artifacts/'):
            # Generated certification outputs are deliberately not candidate inputs.
            continue
        if path.startswith('artifacts/certification/'):
            continue
        dirty.append(line)
    if dirty:
        raise SystemExit('candidate freeze requires a clean committed checkout; dirty entries: ' + '; '.join(dirty[:20]))

    required_files = {
        'contract_manifest': ROOT / 'CONTRACT-MANIFEST.yaml',
        'build_manifest': ROOT / 'BUILD-MANIFEST.yaml',
        'architecture_lock': ROOT / 'ARCHITECTURE-LOCK.yaml',
        'production_certification_contract': ROOT / 'contracts/certification/STH-PRODUCTION-CERTIFICATION-v1.0.yaml',
    }
    missing = [str(p.relative_to(ROOT)) for p in required_files.values() if not p.exists()]
    if missing:
        raise SystemExit('missing candidate-binding inputs: ' + ', '.join(missing))

    payload = {
        'schema_version': 'STH-M7-CANDIDATE-BINDING-v1.0',
        'candidate_version': version,
        'source_revision': source_revision,
        'source_tree': source_tree,
        'input_hashes': {name: sha256_file(path) for name, path in sorted(required_files.items())},
    }
    fingerprint = canonical_hash(payload)
    document = dict(payload)
    document['candidate_fingerprint'] = fingerprint

    if args.expected_fingerprint is not None and args.expected_fingerprint != fingerprint:
        raise SystemExit(
            f'candidate fingerprint mismatch: expected {args.expected_fingerprint}, calculated {fingerprint}'
        )

    out = Path(args.out)
    if not out.is_absolute():
        out = ROOT / out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(document, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    print(json.dumps(document, indent=2, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
