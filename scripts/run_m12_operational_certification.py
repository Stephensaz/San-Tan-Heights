from __future__ import annotations
import json
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

from src.listing_execution.operational_certification import (
    certify_operational_audit,
    load_operational_certification_registry,
)

if __name__=="__main__":
    registry=load_operational_certification_registry("registries/listing_execution/m12-008-operational-certification-v1.0.yaml")
    x=certify_operational_audit(repository_root=".",registry=registry)
    print(json.dumps({
        "package_id":x.package_id,
        "status":x.status,
        "blocking_gaps":list(x.blocking_gaps),
        "evidence_chain_root":x.evidence_chain_root,
        "artifact_manifest_root":x.artifact_manifest_root,
        "operational_certification_root":x.operational_certification_root,
        "final_milestone_decision_issued":x.final_milestone_decision_issued,
        "public_eligible":x.public_eligible,
        "external_action_capability":x.external_action_capability,
        "evidence_sha256":{r.ticket:r.sha256 for r in x.evidence_receipts},
    },sort_keys=True))
    if x.status!="READY_FOR_M12_009" or x.blocking_gaps:
        raise SystemExit(1)
