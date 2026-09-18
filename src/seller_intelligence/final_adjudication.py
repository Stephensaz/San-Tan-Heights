from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
from typing import Mapping
import yaml

from src.seller_intelligence.production_certification import (
    execute_production_certification,
    load_production_certification_registry,
)


def _canonical_hash(payload: object) -> str:
    raw=json.dumps(payload,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode("utf-8")
    return sha256(raw).hexdigest()


def _file_sha(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


@dataclass(frozen=True)
class FinalEvidenceReceipt:
    ticket: str
    path: str
    evidence_id: str
    sha256: str
    status: str
    waivers: int
    open_defects: int


@dataclass(frozen=True)
class SellerIntelligenceFinalAdjudication:
    status: str
    decision: str
    evidence_receipts: tuple[FinalEvidenceReceipt,...]
    contract_sha256: str
    production_candidate_root: str
    end_to_end_fingerprint: str
    promotion_package_fingerprint: str
    rollback_rule_fingerprint: str
    blocking_reasons: tuple[str,...]
    certification_root_hash: str
    public_eligible: bool
    external_action_capability: str


def load_final_adjudication_registry(path: str|Path) -> dict:
    raw=yaml.safe_load(Path(path).read_text())
    if raw.get("seller_final_adjudication_id")!="STH-M11-010-FINAL-ADJUDICATION-v1.0":
        raise ValueError("unexpected M11-010 final adjudication id")
    if str(raw.get("version"))!="1.0.0" or raw.get("status")!="FROZEN":
        raise ValueError("M11-010 registry must be FROZEN v1.0")
    if raw.get("ticket")!="M11-010":
        raise ValueError("M11-010 registry ticket mismatch")
    expected=[f"M11-{i:03d}" for i in range(1,10)]
    if list(raw.get("accepted_evidence") or {})!=expected:
        raise ValueError("M11-010 evidence registry must contain exact ordered M11-001 through M11-009 chain")
    return raw


def _verify_evidence_chain(
    root: Path,
    registry: Mapping[str,object],
) -> tuple[tuple[FinalEvidenceReceipt,...],list[str]]:
    receipts=[]
    blocking=[]
    for ticket,rel_value in registry["accepted_evidence"].items():
        rel=str(rel_value)
        path=root/rel
        if not path.is_file():
            blocking.append(f"{ticket}:EVIDENCE_MISSING")
            continue
        try:
            data=json.loads(path.read_text())
        except Exception:
            blocking.append(f"{ticket}:EVIDENCE_INVALID_JSON")
            continue
        status=str(data.get("status") or "")
        waivers=int(data.get("waivers",-1))
        defects=int(data.get("open_defects",-1))
        if data.get("ticket")!=ticket:
            blocking.append(f"{ticket}:TICKET_ID_MISMATCH")
        if status!="ACCEPTED":
            blocking.append(f"{ticket}:NOT_ACCEPTED")
        if waivers!=0:
            blocking.append(f"{ticket}:WAIVERS_PRESENT")
        if defects!=0:
            blocking.append(f"{ticket}:OPEN_DEFECTS_PRESENT")
        receipts.append(FinalEvidenceReceipt(
            ticket=ticket,
            path=rel,
            evidence_id=str(data.get("evidence_id") or ""),
            sha256=_file_sha(path),
            status=status,
            waivers=waivers,
            open_defects=defects,
        ))
    if len(receipts)!=9:
        blocking.append("EVIDENCE_CHAIN_INCOMPLETE")
    return tuple(receipts),blocking


def execute_final_adjudication(
    *,
    repository_root: str|Path,
    registry: Mapping[str,object],
) -> SellerIntelligenceFinalAdjudication:
    root=Path(repository_root)
    live_version=(root/"VERSION").read_text().strip()
    release_version=str(registry["release_candidate_version"])
    final_evidence_path=root/"certification-evidence/m11-010/final-adjudication-v1.0.json"
    if final_evidence_path.is_file():
        final=json.loads(final_evidence_path.read_text())
        if str(final.get("release_candidate_version") or "")!=release_version:
            raise ValueError("M11-010 release candidate version mismatch")
        if final.get("status")!="ACCEPTED" or final.get("decision")!="SELLER INTELLIGENCE RELEASED":
            raise ValueError("M11-010 final release evidence is not accepted")
    elif live_version!=release_version:
        raise ValueError("M11-010 release candidate version mismatch")

    contract_path=root/"contracts/seller_intelligence/STH-SELLER-INTELLIGENCE-v1.0.yaml"
    contract_sha=_file_sha(contract_path)
    blocking=[]
    if contract_sha!=str(registry["expected_contract_sha256"]):
        blocking.append("SELLER_INTELLIGENCE_CONTRACT_HASH_MISMATCH")

    receipts,evidence_blocking=_verify_evidence_chain(root,registry)
    blocking.extend(evidence_blocking)

    m11_009_evidence_path=root/str(registry["accepted_evidence"]["M11-009"])
    if m11_009_evidence_path.is_file():
        m11_009=json.loads(m11_009_evidence_path.read_text())
        if m11_009.get("decision")!="PRODUCTION CANDIDATE":
            blocking.append("M11-009:PRODUCTION_CANDIDATE_DECISION_MISMATCH")
        if str(m11_009.get("production_candidate_root") or "")!=str(registry["expected_m11_009_production_candidate_root"]):
            blocking.append("M11-009:PRODUCTION_CANDIDATE_ROOT_EVIDENCE_MISMATCH")

    prod_registry_path=root/str(registry["replay"]["production_certification_registry"])
    prod_registry=load_production_certification_registry(prod_registry_path)
    try:
        replay=execute_production_certification(repository_root=root,registry=prod_registry)
    except Exception as exc:
        replay=None
        blocking.append(f"M11-009:REPLAY_EXCEPTION:{type(exc).__name__}")

    if replay is None:
        prod_root=""
        end_to_end=""
        package_fp=""
        rollback_fp=""
    else:
        prod_root=replay.production_candidate_root
        end_to_end=replay.end_to_end_fingerprint
        package_fp=replay.promotion_package_fingerprint
        rollback_fp=replay.rollback_rule_fingerprint
        if replay.status!="PASS" or replay.decision!="PRODUCTION CANDIDATE":
            blocking.append("M11-009:REPLAY_NO_GO")
        if replay.blocking_reasons:
            blocking.append("M11-009:REPLAY_BLOCKING_REASONS")
        if prod_root!=str(registry["expected_m11_009_production_candidate_root"]):
            blocking.append("M11-009:PRODUCTION_CANDIDATE_ROOT_REPRODUCTION_FAILED")
        if replay.public_eligible is not False:
            blocking.append("PUBLIC_STRATEGY_LEAKAGE_BOUNDARY_VIOLATION")
        if replay.external_action_capability!="NONE":
            blocking.append("EXTERNAL_ACTION_BOUNDARY_VIOLATION")

    root_payload={
        "seller_final_adjudication_id":registry["seller_final_adjudication_id"],
        "release_candidate_version":release_version,
        "contract_sha256":contract_sha,
        "accepted_evidence":[
            {
                "ticket":x.ticket,
                "path":x.path,
                "evidence_id":x.evidence_id,
                "sha256":x.sha256,
                "status":x.status,
                "waivers":x.waivers,
                "open_defects":x.open_defects,
            }
            for x in receipts
        ],
        "production_candidate_root":prod_root,
        "end_to_end_fingerprint":end_to_end,
        "promotion_package_fingerprint":package_fp,
        "rollback_rule_fingerprint":rollback_fp,
        "blocking_reasons":sorted(set(blocking)),
        "public_eligible":False,
        "external_action_capability":"NONE",
        "calibration_candidate_auto_promoted":False,
    }
    certification_root=_canonical_hash(root_payload)

    expected_root=str(registry.get("expected_certification_root_hash") or "")
    if expected_root and certification_root!=expected_root:
        blocking.append("M11_FINAL_CERTIFICATION_ROOT_MISMATCH")

    final_blocking=tuple(sorted(set(blocking)))
    passed=not final_blocking
    return SellerIntelligenceFinalAdjudication(
        status="PASS" if passed else "FAIL",
        decision=registry["decision_values"]["pass"] if passed else registry["decision_values"]["fail"],
        evidence_receipts=receipts,
        contract_sha256=contract_sha,
        production_candidate_root=prod_root,
        end_to_end_fingerprint=end_to_end,
        promotion_package_fingerprint=package_fp,
        rollback_rule_fingerprint=rollback_fp,
        blocking_reasons=final_blocking,
        certification_root_hash=certification_root,
        public_eligible=False,
        external_action_capability="NONE",
    )
