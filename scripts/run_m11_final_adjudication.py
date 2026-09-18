from __future__ import annotations
import json
from src.seller_intelligence.final_adjudication import execute_final_adjudication, load_final_adjudication_registry

if __name__=="__main__":
    r=load_final_adjudication_registry("registries/seller_intelligence/m11-010-final-adjudication-v1.0.yaml")
    x=execute_final_adjudication(repository_root=".",registry=r)
    print(json.dumps({
        "status":x.status,
        "decision":x.decision,
        "certification_root_hash":x.certification_root_hash,
        "production_candidate_root":x.production_candidate_root,
        "end_to_end_fingerprint":x.end_to_end_fingerprint,
        "promotion_package_fingerprint":x.promotion_package_fingerprint,
        "rollback_rule_fingerprint":x.rollback_rule_fingerprint,
        "blocking_reasons":list(x.blocking_reasons),
        "accepted_evidence_sha256":{e.ticket:e.sha256 for e in x.evidence_receipts},
        "public_eligible":x.public_eligible,
        "external_action_capability":x.external_action_capability,
    },sort_keys=True))
