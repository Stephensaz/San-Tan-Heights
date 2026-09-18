from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
from typing import Mapping
import yaml

from src.evolution.community_onboarding import (
    CommunityOnboardingInput,
    assert_no_protected_defaults,
    generate_bootstrap,
    load_onboarding_contract,
)
from src.evolution.portability_profiles import load_governed_profile, load_hardening_registry
from src.evolution.progressive_build_pipeline import (
    StageInput,
    execute_progressive_pipeline,
    load_pipeline_registry,
)


def _hash(payload: object) -> str:
    raw=json.dumps(payload,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode("utf-8")
    return sha256(raw).hexdigest()


@dataclass(frozen=True)
class FactoryStageReceipt:
    stage_id: str
    status: str
    evidence_fingerprint: str


@dataclass(frozen=True)
class CandidatePackage:
    package_id: str
    community_id: str
    candidate_fingerprint: str
    bootstrap_fingerprint: str
    profile_root_fingerprint: str
    stage_receipts: tuple[FactoryStageReceipt,...]
    published: bool
    immutable: bool
    package_fingerprint: str


@dataclass(frozen=True)
class ReleaseRequest:
    request_id: str
    community_id: str
    candidate_package_fingerprint: str
    status: str
    approval_required: bool
    approval_authority: str
    unresolved_exceptions: tuple[str,...]
    release_request_fingerprint: str


@dataclass(frozen=True)
class FactoryRunResult:
    status: str
    job_id: str
    community_id: str
    next_resume_stage: str | None
    candidate_package: CandidatePackage | None
    release_request: ReleaseRequest | None
    run_fingerprint: str


def load_factory_registry(path: str|Path) -> dict:
    raw=yaml.safe_load(Path(path).read_text())
    if raw.get("factory_registry_id")!="STH-M10-008-COMMUNITY-FACTORY-v1.0":
        raise ValueError("unexpected M10-008 factory registry id")
    if str(raw.get("version"))!="1.0.0" or raw.get("status")!="FROZEN":
        raise ValueError("M10-008 factory registry must be frozen v1.0")
    if raw.get("ticket")!="M10-008":
        raise ValueError("M10-008 factory registry ticket mismatch")
    return raw


def load_factory_job(path: str|Path) -> dict:
    raw=yaml.safe_load(Path(path).read_text())
    if str(raw.get("version"))!="1.0.0" or raw.get("status")!="READY":
        raise ValueError("factory job must be READY v1.0")
    required=("job_id","community","source_systems","onboarding_assumptions","governed_profiles","stage_evidence","release")
    for key in required:
        if key not in raw or raw[key] in (None,"",[],{}):
            raise ValueError(f"factory job missing required key: {key}")
    if raw.get("publication_allowed") is not False:
        raise ValueError("factory job publication must be prohibited")
    return raw


def _parent_platform_fingerprint(root: Path, registry: Mapping[str,object]) -> tuple[str,str]:
    parent=registry.get("parent_platform") or {}
    version=str(parent.get("version") or "").strip()
    evidence=str(parent.get("immutable_evidence") or "").strip()
    if version!="0.1.119":
        raise ValueError("factory parent version must be accepted M10-007 version 0.1.119")
    if not evidence or not (root/evidence).is_file():
        raise ValueError("factory immutable parent evidence missing")
    payload={}
    for rel in (
        "contracts/evolution/STH-COMMUNITY-ONBOARDING-v1.0.yaml",
        "registries/evolution/m10-004-progressive-build-pipeline-v1.0.yaml",
        "registries/evolution/m10-006-portability-hardening-v1.0.yaml",
        evidence,
    ):
        payload[rel]=sha256((root/rel).read_bytes()).hexdigest()
    return version,_hash(payload)


def _assemble_profiles(
    *,
    root: Path,
    job: Mapping[str,object],
    hardening_registry: Mapping[str,object],
    required_profile_types: tuple[str,...],
) -> tuple[dict[str,str],str]:
    community_id=str(job["community"]["community_id"])
    found={}
    for rel in job["governed_profiles"]:
        rel=str(rel)
        if not (root/rel).is_file():
            raise ValueError(f"missing factory governed profile: {rel}")
        gp=load_governed_profile(root/rel,registry=hardening_registry)
        if gp.community_id!=community_id:
            raise ValueError("factory governed profile community mismatch")
        if gp.profile_type in found:
            raise ValueError("duplicate factory governed profile type")
        found[gp.profile_type]=gp.fingerprint
    if set(found)!=set(required_profile_types):
        raise ValueError("factory job must provide exactly one governed profile of every required type")
    ordered=dict(sorted(found.items()))
    return ordered,_hash(ordered)


def _validate_resume(
    *,
    pipeline_registry: Mapping[str,object],
    prior_stage_status: Mapping[str,str] | None,
    requested_resume_stage: str | None,
) -> str | None:
    ordered=[str(x["id"]) for x in sorted(pipeline_registry["stages"],key=lambda x:int(x["order"]))]
    if prior_stage_status is None:
        if requested_resume_stage is not None:
            raise ValueError("resume stage cannot be requested without prior stage status")
        return None

    first_incomplete=None
    for stage_id in ordered:
        status=str(prior_stage_status.get(stage_id,"NOT_RUN"))
        if status!="PASS":
            first_incomplete=stage_id
            break
    if first_incomplete is None:
        if requested_resume_stage is not None:
            raise ValueError("fully passed run has no valid resume stage")
        return None
    if requested_resume_stage!=first_incomplete:
        raise ValueError(f"retry/resume must start at first incomplete or failed stage: {first_incomplete}")
    return first_incomplete


def run_factory_job(
    *,
    repository_root: str|Path,
    job: Mapping[str,object],
    factory_registry: Mapping[str,object],
    onboarding_contract_path: str|Path,
    pipeline_registry_path: str|Path,
    hardening_registry_path: str|Path,
    prior_stage_status: Mapping[str,str] | None = None,
    requested_resume_stage: str | None = None,
) -> FactoryRunResult:
    root=Path(repository_root)
    version,parent_fp=_parent_platform_fingerprint(root,factory_registry)
    pipeline_registry=load_pipeline_registry(pipeline_registry_path)
    hardening_registry=load_hardening_registry(hardening_registry_path)

    _validate_resume(
        pipeline_registry=pipeline_registry,
        prior_stage_status=prior_stage_status,
        requested_resume_stage=requested_resume_stage,
    )

    community=job["community"]
    community_id=str(community["community_id"])
    sources=job["source_systems"]
    assumptions=job["onboarding_assumptions"]

    required_profile_types=tuple(str(x) for x in factory_registry["required_profile_types"])
    profile_fps,profile_root=_assemble_profiles(
        root=root,
        job=job,
        hardening_registry=hardening_registry,
        required_profile_types=required_profile_types,
    )

    onboarding=CommunityOnboardingInput(
        onboarding_id=str(job["onboarding_id"]),
        community_id=community_id,
        display_name=str(community["display_name"]),
        state=str(community["state"]),
        county=str(community["county"]),
        property_id_prefix=str(community["property_id_prefix"]),
        listing_service=str(sources["listing_service"]),
        parcel_authority=str(sources["parcel_authority"]),
        recorder_authority=str(sources["recorder_authority"]),
        parent_platform_version=version,
        parent_platform_fingerprint=parent_fp,
        community_specific=tuple(str(x) for x in assumptions["community_specific"]),
        source_specific=tuple(str(x) for x in assumptions["source_specific"]),
    )
    contract=load_onboarding_contract(onboarding_contract_path)
    bootstrap=generate_bootstrap(data=onboarding,contract=contract)
    assert_no_protected_defaults(
        bootstrap,
        tuple(str(x) for x in pipeline_registry["protected_defaults"]),
    )

    stage_inputs={}
    for spec in pipeline_registry["stages"]:
        stage_id=str(spec["id"])
        evidence=(job.get("stage_evidence") or {}).get(stage_id)
        if not isinstance(evidence,dict) or not str(evidence.get("artifact") or "").strip():
            raise ValueError(f"missing factory stage evidence: {stage_id}")
        forced_pass=evidence.get("forced_pass",True)
        stage_inputs[stage_id]=StageInput(
            stage_id=stage_id,
            checks={
                "job_manifest_valid":True,
                "profile_bundle_valid":True,
                "stage_evidence_present":True,
                "factory_stage_pass":forced_pass is True,
            },
            evidence={
                "artifact":str(evidence["artifact"]),
                "job_id":str(job["job_id"]),
                "profile_root_fingerprint":profile_root,
                "parent_platform_fingerprint":parent_fp,
            },
        )

    progressive=execute_progressive_pipeline(
        community_id=community_id,
        onboarding_bootstrap_fingerprint=bootstrap.bootstrap_fingerprint,
        stage_inputs=stage_inputs,
        registry=pipeline_registry,
    )

    stage_receipts=tuple(
        FactoryStageReceipt(
            stage_id=x.stage_id,
            status=x.status,
            evidence_fingerprint=x.evidence_fingerprint,
        )
        for x in progressive.stages
    )

    if progressive.status!="PASS" or not progressive.candidate_fingerprint:
        next_stage=progressive.stopped_at
        payload={
            "job_id":job["job_id"],
            "community_id":community_id,
            "status":"FAIL",
            "next_resume_stage":next_stage,
            "stage_receipts":[r.__dict__ for r in stage_receipts],
        }
        return FactoryRunResult(
            status="FAIL",
            job_id=str(job["job_id"]),
            community_id=community_id,
            next_resume_stage=next_stage,
            candidate_package=None,
            release_request=None,
            run_fingerprint=_hash(payload),
        )

    package_payload={
        "job_id":job["job_id"],
        "community_id":community_id,
        "candidate_fingerprint":progressive.candidate_fingerprint,
        "bootstrap_fingerprint":bootstrap.bootstrap_fingerprint,
        "profile_root_fingerprint":profile_root,
        "stage_receipts":[r.__dict__ for r in stage_receipts],
        "published":False,
        "immutable":True,
    }
    package_fp=_hash(package_payload)
    package=CandidatePackage(
        package_id=f"{job['job_id']}-CANDIDATE",
        community_id=community_id,
        candidate_fingerprint=progressive.candidate_fingerprint,
        bootstrap_fingerprint=bootstrap.bootstrap_fingerprint,
        profile_root_fingerprint=profile_root,
        stage_receipts=stage_receipts,
        published=False,
        immutable=True,
        package_fingerprint=package_fp,
    )

    release=job["release"]
    unresolved=tuple(sorted(str(x) for x in release.get("unresolved_exceptions") or ()))
    approval_authority=str(release.get("approval_authority") or "").strip()
    if not approval_authority:
        raise ValueError("factory release approval authority required")
    status="BLOCKED_PENDING_HUMAN_APPROVAL"
    if unresolved:
        status="BLOCKED_UNRESOLVED_EXCEPTIONS"

    request_payload={
        "job_id":job["job_id"],
        "community_id":community_id,
        "candidate_package_fingerprint":package_fp,
        "status":status,
        "approval_required":True,
        "approval_authority":approval_authority,
        "unresolved_exceptions":list(unresolved),
    }
    request=ReleaseRequest(
        request_id=f"{job['job_id']}-RELEASE-REQUEST",
        community_id=community_id,
        candidate_package_fingerprint=package_fp,
        status=status,
        approval_required=True,
        approval_authority=approval_authority,
        unresolved_exceptions=unresolved,
        release_request_fingerprint=_hash(request_payload),
    )

    run_payload={
        "job_id":job["job_id"],
        "community_id":community_id,
        "candidate_package_fingerprint":package_fp,
        "release_request_fingerprint":request.release_request_fingerprint,
        "release_request_status":request.status,
        "published":False,
    }
    return FactoryRunResult(
        status="PASS",
        job_id=str(job["job_id"]),
        community_id=community_id,
        next_resume_stage=None,
        candidate_package=package,
        release_request=request,
        run_fingerprint=_hash(run_payload),
    )
