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
from src.evolution.portability_profiles import (
    load_governed_profile,
    load_hardening_registry,
)
from src.evolution.progressive_build_pipeline import (
    StageInput,
    execute_progressive_pipeline,
    load_pipeline_registry,
)

_ALLOWED_CLASSES = (
    "CORE_REUSABLE",
    "COMMUNITY_CONFIGURABLE",
    "COMMUNITY_SPECIFIC",
    "SOURCE_SPECIFIC",
)
_ALLOWED_ACTIONS = ("REUSE_UNCHANGED", "CONFIGURE", "REMEDIATE")
_FORBIDDEN_PRIOR_PILOT_MARKERS = (
    "RANCHO_VISTOSO",
    "Rancho Vistoso",
    "config/pilots/rancho_vistoso",
    "config/hardening/rancho_vistoso",
)


def _hash(payload: object) -> str:
    raw=json.dumps(payload,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode("utf-8")
    return sha256(raw).hexdigest()


@dataclass(frozen=True)
class ColdStartMetrics:
    total_work_items: int
    reuse_unchanged: int
    configured: int
    remediated: int
    counts_by_class: Mapping[str,int]
    prior_pilot_dependencies: tuple[str,...]


@dataclass(frozen=True)
class ColdStartResult:
    status: str
    community_id: str
    bootstrap_fingerprint: str
    profile_fingerprints: Mapping[str,str]
    progressive_candidate_fingerprint: str
    metrics: ColdStartMetrics
    comparison: Mapping[str,str]
    repeatability_fingerprint: str
    blocking_exceptions: tuple[str,...]


def load_cold_start_profile(path: str|Path) -> dict:
    raw=yaml.safe_load(Path(path).read_text())
    if raw.get("cold_start_id")!="STH-M10-007-DAYBREAK-COLD-START-v1.0":
        raise ValueError("unexpected M10-007 cold-start id")
    if str(raw.get("version"))!="1.0.0" or raw.get("status")!="FROZEN":
        raise ValueError("M10-007 cold-start profile must be frozen v1.0")
    if raw.get("ticket")!="M10-007":
        raise ValueError("M10-007 cold-start ticket mismatch")
    policy=raw.get("cold_start_policy") or {}
    if policy.get("real_community_identity") is not True:
        raise ValueError("cold start must use a real community identity")
    if policy.get("synthetic_property_corpus_only") is not True:
        raise ValueError("cold-start property corpus must remain synthetic")
    if policy.get("proprietary_mls_records_used") is not False:
        raise ValueError("cold start may not imply proprietary MLS data access")
    if policy.get("homeowner_personal_data_used") is not False:
        raise ValueError("cold start may not use homeowner personal data")
    if policy.get("publication_allowed") is not False:
        raise ValueError("cold-start publication must be prohibited")
    if policy.get("prior_pilot_artifacts_allowed") is not False:
        raise ValueError("prior-pilot artifacts must be prohibited")
    return raw


def _immutable_platform_fingerprint(root: Path, profile: Mapping[str,object]) -> tuple[str,str]:
    parent=profile.get("parent_platform") or {}
    version=str(parent.get("version") or "").strip()
    evidence=str(parent.get("immutable_evidence") or "").strip()
    if version!="0.1.118":
        raise ValueError("cold-start parent version must be accepted M10-006 version 0.1.118")
    if not evidence or not (root/evidence).is_file():
        raise ValueError("cold-start parent evidence missing")
    payload={}
    for rel in (
        "contracts/evolution/STH-COMMUNITY-ONBOARDING-v1.0.yaml",
        "registries/evolution/m10-004-progressive-build-pipeline-v1.0.yaml",
        "registries/evolution/m10-006-portability-hardening-v1.0.yaml",
        evidence,
    ):
        payload[rel]=sha256((root/rel).read_bytes()).hexdigest()
    return version,_hash(payload)


def _scan_prior_pilot_dependencies(profile: Mapping[str,object], profile_payloads: Mapping[str,object]) -> tuple[str,...]:
    raw=json.dumps({"cold_start":profile,"governed_profiles":profile_payloads},sort_keys=True)
    return tuple(sorted(marker for marker in _FORBIDDEN_PRIOR_PILOT_MARKERS if marker in raw))


def _measure(profile: Mapping[str,object]) -> ColdStartMetrics:
    items=tuple(profile.get("work_items") or ())
    if not items:
        raise ValueError("cold-start work items required")
    counts={x:0 for x in _ALLOWED_CLASSES}
    actions={x:0 for x in _ALLOWED_ACTIONS}
    seen=set()
    for item in items:
        item_id=str(item.get("id") or "")
        cls=str(item.get("component_class") or "")
        action=str(item.get("action") or "")
        artifact=str(item.get("artifact") or "")
        if not item_id or item_id in seen:
            raise ValueError("cold-start work item ids must be unique and nonblank")
        seen.add(item_id)
        if cls not in counts:
            raise ValueError(f"invalid cold-start classification: {cls}")
        if action not in actions:
            raise ValueError(f"invalid cold-start action: {action}")
        if not artifact:
            raise ValueError(f"cold-start artifact required: {item_id}")
        counts[cls]+=1
        actions[action]+=1
    return ColdStartMetrics(
        total_work_items=len(items),
        reuse_unchanged=actions["REUSE_UNCHANGED"],
        configured=actions["CONFIGURE"],
        remediated=actions["REMEDIATE"],
        counts_by_class=dict(sorted(counts.items())),
        prior_pilot_dependencies=(),
    )


def execute_cold_start(
    *,
    repository_root: str|Path,
    profile: Mapping[str,object],
    onboarding_contract_path: str|Path,
    pipeline_registry_path: str|Path,
    hardening_registry_path: str|Path,
) -> ColdStartResult:
    root=Path(repository_root)
    community=profile["community"]
    sources=profile["source_systems"]
    assumptions=profile["onboarding_assumptions"]
    version,parent_fp=_immutable_platform_fingerprint(root,profile)

    hardening_registry=load_hardening_registry(hardening_registry_path)
    governed={}
    profile_payloads={}
    for rel in profile.get("governed_profiles") or ():
        rel=str(rel)
        if any(marker in rel for marker in _FORBIDDEN_PRIOR_PILOT_MARKERS):
            raise ValueError(f"prior-pilot artifact dependency prohibited: {rel}")
        if not (root/rel).is_file():
            raise ValueError(f"missing cold-start governed profile: {rel}")
        gp=load_governed_profile(root/rel,registry=hardening_registry)
        if gp.community_id!=community["community_id"]:
            raise ValueError("cold-start governed profile community mismatch")
        if gp.profile_type in governed:
            raise ValueError("duplicate cold-start governed profile type")
        governed[gp.profile_type]=gp
        profile_payloads[gp.profile_type]=gp.payload

    required_types=set(hardening_registry["profile_types"])
    if set(governed)!=required_types:
        raise ValueError("cold start must provide exactly one governed profile of every M10-006 profile type")

    dependencies=_scan_prior_pilot_dependencies(profile,profile_payloads)
    if dependencies:
        raise ValueError(f"prior-pilot dependency detected: {dependencies}")

    onboarding=CommunityOnboardingInput(
        onboarding_id="ONB-DAYBREAK-UT-001",
        community_id=str(community["community_id"]),
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
    pipeline_registry=load_pipeline_registry(pipeline_registry_path)
    assert_no_protected_defaults(
        bootstrap,
        tuple(str(x) for x in pipeline_registry["protected_defaults"]),
    )

    provenance=profile.get("source_provenance") or {}
    if set(provenance)!={"community_authority","listing_service","parcel_authority","recorder_authority"}:
        raise ValueError("cold-start source provenance incomplete")
    for name,item in provenance.items():
        if not str(item.get("name") or "").strip() or not str(item.get("url") or "").startswith("https://"):
            raise ValueError(f"invalid cold-start source provenance: {name}")

    metrics=_measure(profile)
    if metrics.remediated!=0:
        raise ValueError("cold start requires manual remediation despite hardened profile interfaces")

    stage_evidence=profile.get("stage_evidence") or {}
    stage_inputs={}
    profile_fps={k:v.fingerprint for k,v in sorted(governed.items())}
    profile_root=_hash(profile_fps)
    for spec in pipeline_registry["stages"]:
        stage_id=str(spec["id"])
        evidence=stage_evidence.get(stage_id)
        if not isinstance(evidence,dict) or not str(evidence.get("artifact") or "").strip():
            raise ValueError(f"missing cold-start stage evidence: {stage_id}")
        stage_inputs[stage_id]=StageInput(
            stage_id=stage_id,
            checks={
                "cold_start_evidence_present":True,
                "governed_profiles_valid":True,
                "manual_remediation_zero":True,
                "prior_pilot_dependency_zero":True,
                "synthetic_data_boundary_preserved":True,
            },
            evidence={
                "artifact":str(evidence["artifact"]),
                "cold_start_id":str(profile["cold_start_id"]),
                "parent_platform_fingerprint":parent_fp,
                "governed_profile_root":profile_root,
            },
        )

    progressive=execute_progressive_pipeline(
        community_id=str(community["community_id"]),
        onboarding_bootstrap_fingerprint=bootstrap.bootstrap_fingerprint,
        stage_inputs=stage_inputs,
        registry=pipeline_registry,
    )
    if progressive.status!="PASS" or not progressive.candidate_fingerprint:
        raise ValueError("M10-004 cold-start progressive pipeline did not pass")

    comparators=profile.get("comparators") or {}
    pre=int(comparators["pre_hardening_manual_remediation"])
    post=int(comparators["post_hardening_manual_remediation"])
    comparison={
        "pre_hardening":f"{pre}/{comparators['pre_hardening_total_work_items']}",
        "post_hardening":f"{post}/{comparators['post_hardening_total_work_items']}",
        "third_community_cold_start":f"{metrics.remediated}/{metrics.total_work_items}",
    }
    payload={
        "cold_start_id":profile["cold_start_id"],
        "community_id":community["community_id"],
        "parent_platform_fingerprint":parent_fp,
        "bootstrap_fingerprint":bootstrap.bootstrap_fingerprint,
        "governed_profiles":profile_fps,
        "progressive_candidate_fingerprint":progressive.candidate_fingerprint,
        "metrics":{
            "total_work_items":metrics.total_work_items,
            "reuse_unchanged":metrics.reuse_unchanged,
            "configured":metrics.configured,
            "remediated":metrics.remediated,
            "counts_by_class":dict(metrics.counts_by_class),
        },
        "comparison":comparison,
    }
    return ColdStartResult(
        status="PASS",
        community_id=str(community["community_id"]),
        bootstrap_fingerprint=bootstrap.bootstrap_fingerprint,
        profile_fingerprints=profile_fps,
        progressive_candidate_fingerprint=progressive.candidate_fingerprint,
        metrics=metrics,
        comparison=comparison,
        repeatability_fingerprint=_hash(payload),
        blocking_exceptions=(),
    )
