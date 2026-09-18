from __future__ import annotations
import json
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

from src.listing_execution.final_certification import execute_final_certification, load_final_certification_registry

if __name__=="__main__":
    r=load_final_certification_registry("registries/listing_execution/m12-009-final-certification-v1.0.yaml")
    x=execute_final_certification(repository_root=".",registry=r)
    print(json.dumps({
        "status":x.status,
        "decision":x.decision,
        "certification_root_hash":x.certification_root_hash,
        "m12_008_operational_root":x.m12_008_operational_root,
        "blocking_reasons":list(x.blocking_reasons),
        "coverage":list(x.coverage),
        "stages":[{"stage_id":s.stage_id,"status":s.status,"checks":list(s.checks),"blocking_reasons":list(s.blocking_reasons),"stage_fingerprint":s.stage_fingerprint} for s in x.stage_results],
        "evidence_sha256":dict(x.evidence_sha256),
    },sort_keys=True))
    if x.status!="PASS" or x.decision!="GO" or x.blocking_reasons:
        raise SystemExit(1)
