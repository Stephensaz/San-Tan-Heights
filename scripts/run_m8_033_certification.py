from pathlib import Path
import argparse
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.presentation.certification import M8033CertificationRunner, write_bundle
MANIFEST = ROOT / "registries" / "presentation" / "m8-033-certification-v1.0.yaml"

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="certification-evidence/m8-033/latest.json")
    args = parser.parse_args()
    runner = M8033CertificationRunner(ROOT, MANIFEST)
    bundle = runner.run(verify_source_commit=True)
    write_bundle(bundle, ROOT / args.output)
    print(f"M8-033 verdict: {bundle.verdict}")
    print(f"M8-033 evidence hash: {bundle.evidence_hash}")
    for item in bundle.layers:
        print(f"Layer {item.key}: {'PASS' if item.passed else 'FAIL'} :: {' | '.join(item.details)}")
    for gate in bundle.stage_gates:
        print(f"Gate {gate.key}: {'PASS' if gate.passed else 'FAIL'} :: {' | '.join(gate.details)}")
    print(f"Acceptance criteria: {sum(item.passed for item in bundle.acceptance_criteria)}/12 PASS")
    if bundle.open_defects:
        print("Open defects:")
        for defect in bundle.open_defects:
            print(f"- {defect}")
    return 0 if bundle.verdict == "PASS / GO" else 1

if __name__ == "__main__":
    sys.exit(main())
