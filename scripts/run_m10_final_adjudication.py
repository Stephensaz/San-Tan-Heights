from __future__ import annotations

import json

from src.evolution.milestone10_adjudication import (
    execute_final_adjudication,
    load_adjudication_registry,
)

REGISTRY="registries/evolution/m10-010-final-adjudication-v1.0.yaml"

if __name__=="__main__":
    registry=load_adjudication_registry(REGISTRY)
    result=execute_final_adjudication(repository_root=".",registry=registry)
    print(json.dumps({
        "status":result.status,
        "decision":result.decision,
        "certification_root_hash":result.certification_root_hash,
        "portfolio_fingerprint":result.portfolio_fingerprint,
        "portfolio_decision":result.portfolio_decision,
        "factory_replay_fingerprints":dict(result.factory_replay_fingerprints),
        "blocking_reasons":list(result.blocking_reasons),
        "ticket_evidence_sha256":{x.ticket:x.sha256 for x in result.ticket_receipts},
    },sort_keys=True))
