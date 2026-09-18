from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
import re
from typing import Mapping
import yaml

from src.evolution.community_factory import (
    FactoryRunResult,
    load_factory_job,
    load_factory_registry,
    run_factory_job,
)

_SHA256=re.compile(r"^[0-9a-f]{64}$")


def _hash(payload: object) -> str:
    raw=json.dumps(payload,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode("utf-8")
    return sha256(raw).hexdigest()


@dataclass(frozen=True)
class PortfolioMemberResult:
    member_id: str
    community_id: str
    namespace: str
    status: str
    reasons: tuple[str,...]
    candidate_fingerprint: str | None
    package_fingerprint: str | None
    release_request_fingerprint: str | None
    approval_id: str
    approval_authority: str
    rollback_baseline_id: str
    rollback_baseline_fingerprint: str
    rollback_eligible: bool
    member_fingerprint: str


@dataclass(frozen=True)
class PortfolioCertificationResult:
    portfolio_id: str
    status: str
    decision: str
    members: tuple[PortfolioMemberResult,...]
    published: bool
    readiness_only: bool
    portfolio_fingerprint: str


def load_portfolio_registry(path: str|Path) -> dict:
    raw=yaml.safe_load(Path(path).read_text())
    if raw.get("portfolio_registry_id")!="STH-M10-009-PORTFOLIO-CERTIFICATION-v1.0":
        raise ValueError("unexpected M10-009 portfolio registry id")
    if str(raw.get("version"))!="1.0.0" or raw.get("status")!="FROZEN":
        raise ValueError("M10-009 portfolio registry must be frozen v1.0")
    if raw.get("ticket")!="M10-009":
        raise ValueError("M10-009 portfolio registry ticket mismatch")
    return raw


def load_portfolio_manifest(path: str|Path) -> dict:
    raw=yaml.safe_load(Path(path).read_text())
    if str(raw.get("version"))!="1.0.0" or raw.get("status")!="READY":
        raise ValueError("portfolio manifest must be READY v1.0")
    if raw.get("publication_allowed") is not False:
        raise ValueError("portfolio publication must be prohibited")
    members=raw.get("members")
    if not isinstance(members,list) or len(members)<2:
        raise ValueError("portfolio requires at least two members")
    return raw


def _parent_platform_fingerprint(root: Path, registry: Mapping[str,object]) -> str:
    parent=registry.get("parent_platform") or {}
    version=str(parent.get("version") or "").strip()
    evidence=str(parent.get("immutable_evidence") or "").strip()
    if version!="0.1.120":
        raise ValueError("portfolio parent version must be accepted M10-008 version 0.1.120")
    if not evidence or not (root/evidence).is_file():
        raise ValueError("portfolio immutable parent evidence missing")
    payload={}
    for rel in (
        "registries/evolution/m10-008-community-factory-v1.0.yaml",
        evidence,
    ):
        payload[rel]=sha256((root/rel).read_bytes()).hexdigest()
    return _hash(payload)


def _validate_member_static(member: Mapping[str,object]) -> None:
    required=("member_id","factory_job","namespace","freshness","approval","rollback")
    for key in required:
        if key not in member or member[key] in (None,"",{},[]):
            raise ValueError(f"portfolio member missing required key: {key}")
    rollback=member["rollback"]
    fp=str(rollback.get("baseline_fingerprint") or "")
    if not _SHA256.fullmatch(fp):
        raise ValueError("rollback baseline fingerprint must be sha256")
    if rollback.get("rollback_eligible") is not True:
        raise ValueError("portfolio member rollback eligibility required")


def _adjudicate_member(
    *,
    member: Mapping[str,object],
    factory_result: FactoryRunResult,
) -> PortfolioMemberResult:
    _validate_member_static(member)
    reasons=[]
    package=factory_result.candidate_package
    request=factory_result.release_request
    approval=member["approval"]
    freshness=member["freshness"]
    rollback=member["rollback"]

    if factory_result.status!="PASS":
        reasons.append("FACTORY_FAIL")
    if package is None:
        reasons.append("CANDIDATE_PACKAGE_MISSING")
    if request is None:
        reasons.append("RELEASE_REQUEST_MISSING")
    if package is not None and package.published is not False:
        reasons.append("PACKAGE_ALREADY_PUBLISHED")
    if package is not None and package.immutable is not True:
        reasons.append("PACKAGE_NOT_IMMUTABLE")
    if str(freshness.get("status"))!="CURRENT":
        reasons.append("STALE")
    if request is not None and request.unresolved_exceptions:
        reasons.append("UNRESOLVED_EXCEPTIONS")
    if str(approval.get("status"))!="APPROVED":
        reasons.append("UNAPPROVED")

    authority=str(approval.get("authority") or "")
    approval_id=str(approval.get("approval_id") or "")
    if not authority or not approval_id:
        reasons.append("APPROVAL_RECORD_INCOMPLETE")
    if request is not None and authority!=request.approval_authority:
        reasons.append("APPROVAL_AUTHORITY_MISMATCH")

    community_id=factory_result.community_id
    namespace=str(member["namespace"])
    if not namespace.endswith("/"+community_id):
        reasons.append("NAMESPACE_COMMUNITY_MISMATCH")

    candidate_fp=package.candidate_fingerprint if package else None
    package_fp=package.package_fingerprint if package else None
    request_fp=request.release_request_fingerprint if request else None
    status="PASS" if not reasons else "FAIL"

    payload={
        "member_id":member["member_id"],
        "community_id":community_id,
        "namespace":namespace,
        "status":status,
        "reasons":sorted(reasons),
        "candidate_fingerprint":candidate_fp,
        "package_fingerprint":package_fp,
        "release_request_fingerprint":request_fp,
        "approval_id":approval_id,
        "approval_authority":authority,
        "rollback_baseline_id":rollback["baseline_id"],
        "rollback_baseline_fingerprint":rollback["baseline_fingerprint"],
        "rollback_eligible":rollback["rollback_eligible"],
    }
    return PortfolioMemberResult(
        member_id=str(member["member_id"]),
        community_id=community_id,
        namespace=namespace,
        status=status,
        reasons=tuple(sorted(reasons)),
        candidate_fingerprint=candidate_fp,
        package_fingerprint=package_fp,
        release_request_fingerprint=request_fp,
        approval_id=approval_id,
        approval_authority=authority,
        rollback_baseline_id=str(rollback["baseline_id"]),
        rollback_baseline_fingerprint=str(rollback["baseline_fingerprint"]),
        rollback_eligible=True,
        member_fingerprint=_hash(payload),
    )


def certify_portfolio(
    *,
    repository_root: str|Path,
    manifest: Mapping[str,object],
    portfolio_registry: Mapping[str,object],
    factory_registry_path: str|Path,
    onboarding_contract_path: str|Path,
    pipeline_registry_path: str|Path,
    hardening_registry_path: str|Path,
) -> PortfolioCertificationResult:
    root=Path(repository_root)
    parent_fp=_parent_platform_fingerprint(root,portfolio_registry)
    factory_registry=load_factory_registry(factory_registry_path)

    seen_member_ids=set()
    seen_communities=set()
    seen_namespaces=set()
    seen_approvals=set()
    results=[]

    for member in manifest["members"]:
        _validate_member_static(member)
        member_id=str(member["member_id"])
        if member_id in seen_member_ids:
            raise ValueError("portfolio member ids must be unique")
        seen_member_ids.add(member_id)

        job_path=str(member["factory_job"])
        if not (root/job_path).is_file():
            raise ValueError(f"missing portfolio factory job: {job_path}")
        job=load_factory_job(root/job_path)
        factory_result=run_factory_job(
            repository_root=root,
            job=job,
            factory_registry=factory_registry,
            onboarding_contract_path=onboarding_contract_path,
            pipeline_registry_path=pipeline_registry_path,
            hardening_registry_path=hardening_registry_path,
        )
        community_id=factory_result.community_id
        if community_id in seen_communities:
            raise ValueError("portfolio community ids must be unique")
        seen_communities.add(community_id)

        namespace=str(member["namespace"])
        if namespace in seen_namespaces:
            raise ValueError("portfolio namespaces must be unique")
        seen_namespaces.add(namespace)

        approval_id=str(member["approval"].get("approval_id") or "")
        if approval_id in seen_approvals:
            raise ValueError("portfolio approval records must be community-scoped and unique")
        seen_approvals.add(approval_id)

        results.append(_adjudicate_member(member=member,factory_result=factory_result))

    # Explicitly prevent cross-community candidate/package/rollback aliasing.
    for field_name in ("candidate_fingerprint","package_fingerprint","rollback_baseline_fingerprint"):
        values=[getattr(x,field_name) for x in results]
        nonnull=[x for x in values if x is not None]
        if len(nonnull)!=len(set(nonnull)):
            raise ValueError(f"cross-community {field_name} collision")

    all_pass=all(x.status=="PASS" for x in results)
    status="PASS" if all_pass else "FAIL"
    decision="GO" if all_pass else "NO-GO"
    payload={
        "portfolio_id":manifest["portfolio_id"],
        "parent_platform_fingerprint":parent_fp,
        "status":status,
        "decision":decision,
        "members":[
            {
                "member_id":x.member_id,
                "community_id":x.community_id,
                "namespace":x.namespace,
                "status":x.status,
                "reasons":list(x.reasons),
                "member_fingerprint":x.member_fingerprint,
                "rollback_baseline_fingerprint":x.rollback_baseline_fingerprint,
            }
            for x in sorted(results,key=lambda x:x.member_id)
        ],
        "published":False,
        "readiness_only":True,
    }
    return PortfolioCertificationResult(
        portfolio_id=str(manifest["portfolio_id"]),
        status=status,
        decision=decision,
        members=tuple(results),
        published=False,
        readiness_only=True,
        portfolio_fingerprint=_hash(payload),
    )
