from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
from typing import Mapping
import yaml

from src.evolution.community_factory import (
    load_factory_job,
    load_factory_registry,
    run_factory_job,
)
from src.evolution.portfolio_certification import (
    certify_portfolio,
    load_portfolio_manifest,
    load_portfolio_registry,
)


def _canonical_hash(payload: object) -> str:
    raw=json.dumps(payload,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode("utf-8")
    return sha256(raw).hexdigest()


def _file_sha(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


@dataclass(frozen=True)
class TicketEvidenceReceipt:
    ticket: str
    path: str
    evidence_id: str
    sha256: str
    status: str
    waivers: int
    open_defects: int


@dataclass(frozen=True)
class FinalAdjudicationResult:
    status: str
    decision: str
    ticket_receipts: tuple[TicketEvidenceReceipt,...]
    factory_replay_fingerprints: Mapping[str,str]
    portfolio_fingerprint: str
    portfolio_decision: str
    blocking_reasons: tuple[str,...]
    certification_root_hash: str


def load_adjudication_registry(path: str|Path) -> dict:
    raw=yaml.safe_load(Path(path).read_text())
    if raw.get("adjudication_registry_id")!="STH-M10-010-FINAL-ADJUDICATION-v1.0":
        raise ValueError("unexpected M10-010 adjudication registry id")
    if str(raw.get("version"))!="1.0.0" or raw.get("status")!="FROZEN":
        raise ValueError("M10-010 adjudication registry must be frozen v1.0")
    if raw.get("ticket")!="M10-010":
        raise ValueError("M10-010 adjudication registry ticket mismatch")
    expected=[f"M10-{i:03d}" for i in range(1,10)]
    if list(raw.get("accepted_evidence") or {})!=expected:
        raise ValueError("M10-010 evidence registry must contain exact ordered M10-001 through M10-009 chain")
    return raw


def _verify_evidence_chain(root: Path, registry: Mapping[str,object]) -> tuple[tuple[TicketEvidenceReceipt,...],list[str]]:
    receipts=[]
    blocking=[]
    for ticket,path_value in registry["accepted_evidence"].items():
        rel=str(path_value)
        path=root/rel
        if not path.is_file():
            blocking.append(f"{ticket}:EVIDENCE_MISSING")
            continue
        try:
            data=json.loads(path.read_text())
        except Exception:
            blocking.append(f"{ticket}:EVIDENCE_INVALID_JSON")
            continue
        evidence_ticket=str(data.get("ticket") or "")
        status=str(data.get("status") or "")
        waivers=int(data.get("waivers",-1))
        defects=int(data.get("open_defects",-1))
        if evidence_ticket!=ticket:
            blocking.append(f"{ticket}:TICKET_ID_MISMATCH")
        if status!="ACCEPTED":
            blocking.append(f"{ticket}:NOT_ACCEPTED")
        if waivers!=0:
            blocking.append(f"{ticket}:WAIVERS_PRESENT")
        if defects!=0:
            blocking.append(f"{ticket}:OPEN_DEFECTS_PRESENT")
        receipts.append(TicketEvidenceReceipt(
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
) -> FinalAdjudicationResult:
    root=Path(repository_root)
    version=(root/"VERSION").read_text().strip()
    if version!=str(registry["release_candidate_version"]):
        raise ValueError("M10-010 release candidate version mismatch")

    receipts,blocking=_verify_evidence_chain(root,registry)
    replay=registry["replay"]

    factory_registry=load_factory_registry(root/str(replay["factory_registry"]))
    factory_fps={}
    for job_rel in replay["factory_jobs"]:
        job=load_factory_job(root/str(job_rel))
        result=run_factory_job(
            repository_root=root,
            job=job,
            factory_registry=factory_registry,
            onboarding_contract_path=root/str(replay["onboarding_contract"]),
            pipeline_registry_path=root/str(replay["progressive_pipeline_registry"]),
            hardening_registry_path=root/str(replay["hardening_registry"]),
        )
        if result.status!="PASS" or result.candidate_package is None or result.release_request is None:
            blocking.append(f"{result.community_id}:FACTORY_REPLAY_FAIL")
            continue
        if result.candidate_package.published is not False:
            blocking.append(f"{result.community_id}:FACTORY_PACKAGE_PUBLISHED")
        factory_fps[result.community_id]=result.run_fingerprint

    portfolio_registry=load_portfolio_registry(root/str(replay["portfolio_registry"]))
    portfolio_manifest=load_portfolio_manifest(root/str(replay["portfolio_manifest"]))
    portfolio=certify_portfolio(
        repository_root=root,
        manifest=portfolio_manifest,
        portfolio_registry=portfolio_registry,
        factory_registry_path=root/str(replay["factory_registry"]),
        onboarding_contract_path=root/str(replay["onboarding_contract"]),
        pipeline_registry_path=root/str(replay["progressive_pipeline_registry"]),
        hardening_registry_path=root/str(replay["hardening_registry"]),
    )
    if portfolio.status!="PASS" or portfolio.decision!="GO":
        blocking.append("PORTFOLIO_REPLAY_NO_GO")
    if portfolio.published is not False or portfolio.readiness_only is not True:
        blocking.append("PORTFOLIO_RELEASE_BOUNDARY_VIOLATION")

    root_payload={
        "adjudication_registry_id":registry["adjudication_registry_id"],
        "release_candidate_version":registry["release_candidate_version"],
        "ticket_evidence":[
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
        "factory_replay_fingerprints":dict(sorted(factory_fps.items())),
        "portfolio_fingerprint":portfolio.portfolio_fingerprint,
        "portfolio_decision":portfolio.decision,
        "blocking_reasons":sorted(set(blocking)),
        "published":False,
    }
    certification_root=_canonical_hash(root_payload)
    final_blocking=tuple(sorted(set(blocking)))
    passed=not final_blocking
    return FinalAdjudicationResult(
        status="PASS" if passed else "FAIL",
        decision="PLATFORM RELEASED" if passed else "NO-GO",
        ticket_receipts=receipts,
        factory_replay_fingerprints=dict(sorted(factory_fps.items())),
        portfolio_fingerprint=portfolio.portfolio_fingerprint,
        portfolio_decision=portfolio.decision,
        blocking_reasons=final_blocking,
        certification_root_hash=certification_root,
    )
