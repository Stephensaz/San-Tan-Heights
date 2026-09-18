#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.activation.final_certification import run_repository_final_certification


def main() -> int:
    ap = argparse.ArgumentParser(description="Execute the frozen M9-012 Production Activation Certification.")
    ap.add_argument("--output", required=True)
    ap.add_argument("--source-revision", required=True)
    args = ap.parse_args()

    result = run_repository_final_certification(ROOT)
    payload = {
        "certification_id": "STH-M9-012-PRODUCTION-ACTIVATION-CERTIFICATION-v1.0",
        "source_revision": args.source_revision,
        "status": result.status,
        "verdict": "PASS / GO" if result.verdict == "GO" else "FAIL / NO-GO",
        "candidate_fingerprint": result.candidate_fingerprint,
        "certification_root_hash": result.certification_root_hash,
        "evidence_hashes": dict(result.evidence_hashes),
        "check_statuses": dict(result.check_statuses),
        "reason_codes": list(result.reason_codes),
    }
    Path(args.output).write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if result.status == "PASS" and result.verdict == "GO" else 2


if __name__ == "__main__":
    raise SystemExit(main())
