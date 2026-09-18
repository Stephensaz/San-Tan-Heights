from __future__ import annotations
import json
from src.seller_intelligence.production_certification import execute_production_certification, load_production_certification_registry

if __name__=="__main__":
    r=load_production_certification_registry("registries/seller_intelligence/m11-009-production-certification-v1.0.yaml")
    x=execute_production_certification(repository_root=".",registry=r)
    print(json.dumps({
        "status":x.status,
        "decision":x.decision,
        "production_candidate_root":x.production_candidate_root,
        "end_to_end_fingerprint":x.end_to_end_fingerprint,
        "promotion_package_fingerprint":x.promotion_package_fingerprint,
        "rollback_rule_fingerprint":x.rollback_rule_fingerprint,
        "negative_controls":list(x.negative_controls),
        "blocking_reasons":list(x.blocking_reasons),
        "evidence_sha256":{e.ticket:e.sha256 for e in x.evidence_receipts},
    },sort_keys=True))
