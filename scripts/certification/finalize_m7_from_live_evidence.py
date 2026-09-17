#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.production_certification.certification import FinalCertificationPolicy, load_live_postgresql_evidence
from src.production_certification.certification.finalizer import M7LiveEvidenceFinalizer


def run_checked(command: list[str]) -> str:
    cp = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
    if cp.returncode != 0:
        sys.stderr.write(cp.stdout)
        sys.stderr.write(cp.stderr)
        raise SystemExit(cp.returncode)
    return cp.stdout


def main() -> int:
    ap = argparse.ArgumentParser(description='Validate candidate-bound live PostgreSQL evidence and finalize M7 only when every gate is satisfied.')
    ap.add_argument('--evidence', required=True)
    ap.add_argument('--candidate-fingerprint', required=True)
    ap.add_argument('--source-revision', required=True)
    ap.add_argument('--apply', action='store_true', help='Apply M7 ACCEPTED / M8 IN_PROGRESS status transition after validation and tests.')
    args = ap.parse_args()

    policy = FinalCertificationPolicy.load(ROOT / 'registries/production-certification/final-certification-policy.yaml')
    evidence = load_live_postgresql_evidence(args.evidence)
    finalizer = M7LiveEvidenceFinalizer()
    assessment = finalizer.assess(
        policy=policy,
        evidence=evidence,
        candidate_fingerprint=args.candidate_fingerprint,
        source_revision=args.source_revision,
    )
    print(json.dumps({
        'status': assessment.status,
        'eligible': assessment.eligible,
        'reason_codes': list(assessment.reason_codes),
        'check_statuses': dict(assessment.check_statuses),
        'assessment_fingerprint': assessment.assessment_fingerprint,
    }, indent=2, sort_keys=True))
    if not assessment.eligible:
        return 2
    if not args.apply:
        return 0

    test_out = run_checked(['pytest', '-q'])
    count_line = next((line for line in reversed(test_out.splitlines()) if ' passed' in line), '')
    try:
        test_count = int(count_line.split()[0])
    except Exception:
        raise SystemExit('could not determine passing test count from pytest output')
    run_checked(['python', 'scripts_validate_repo.py'])
    next_version = finalizer.apply_repository_transition(
        repo_root=ROOT,
        evidence_path=args.evidence,
        assessment=assessment,
        test_count=test_count,
    )
    print(json.dumps({
        'applied': True,
        'version': next_version,
        'm7': 'ACCEPTED',
        'm8': 'IN_PROGRESS',
        'current_ticket': 'M8-001',
    }, indent=2, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
