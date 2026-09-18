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


def _hash(payload: object) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return sha256(raw).hexdigest()


def platform_fingerprint(root: str | Path) -> str:
    root = Path(root)
    payload = {}
    for rel in (
        "contracts/evolution/STH-COMMUNITY-ONBOARDING-v1.0.yaml",
        "registries/evolution/m10-004-progressive-build-pipeline-v1.0.yaml",
        "certification-evidence/m10-004/progressive-build-pipeline-acceptance-v1.0.json",
    ):
        payload[rel] = sha256((root / rel).read_bytes()).hexdigest()
    return _hash(payload)


@dataclass(frozen=True)
class PortabilityMetrics:
    total_work_items: int
    counts_by_class: Mapping[str, int]
    reuse_unchanged: int
    configured: int
    remediated: int
    manual_remediation_items: tuple[str, ...]
    reuse_fraction: str
    remediation_fraction: str


@dataclass(frozen=True)
class PortabilityPilotResult:
    pilot_id: str
    community_id: str
    bootstrap_fingerprint: str
    progressive_candidate_fingerprint: str
    metrics: PortabilityMetrics
    pilot_fingerprint: str
    unresolved_remediation: tuple[str, ...]
    blocking_exceptions: tuple[str, ...]
    status: str


def load_pilot_profile(path: str | Path) -> dict:
    raw = yaml.safe_load(Path(path).read_text())
    if raw.get("pilot_id") != "STH-M10-005-RANCHO-VISTOSO-v1.0":
        raise ValueError("unexpected M10-005 pilot id")
    if str(raw.get("version")) != "1.0.0" or raw.get("status") != "FROZEN":
        raise ValueError("M10-005 pilot profile must be frozen v1.0")
    if raw.get("ticket") != "M10-005":
        raise ValueError("pilot ticket mismatch")
    if raw.get("community", {}).get("real_community") is not True:
        raise ValueError("M10-005 requires a real-community pilot")
    policy = raw.get("pilot_data_policy") or {}
    if policy.get("synthetic_property_corpus_only") is not True:
        raise ValueError("pilot property corpus must remain synthetic")
    if policy.get("proprietary_mls_records_used") is not False:
        raise ValueError("pilot must not imply proprietary MLS data access")
    if policy.get("homeowner_personal_data_used") is not False:
        raise ValueError("pilot must not use homeowner personal data")
    if policy.get("publication_allowed") is not False:
        raise ValueError("pilot publication must be prohibited")
    return raw


def _ratio(numerator: int, denominator: int) -> str:
    if denominator <= 0:
        raise ValueError("work item denominator must be positive")
    return f"{numerator}/{denominator}"


def _measure(profile: Mapping[str, object]) -> PortabilityMetrics:
    items = tuple(profile.get("work_items") or ())
    if not items:
        raise ValueError("pilot work items required")

    counts = {name: 0 for name in _ALLOWED_CLASSES}
    actions = {"REUSE_UNCHANGED": 0, "CONFIGURE": 0, "REMEDIATE": 0}
    seen = set()
    remediation_ids = []

    for item in items:
        item_id = str(item.get("id") or "")
        cls = str(item.get("component_class") or "")
        action = str(item.get("action") or "")
        artifact = str(item.get("artifact") or "")
        if not item_id or item_id in seen:
            raise ValueError("work item ids must be unique and nonblank")
        seen.add(item_id)
        if cls not in counts:
            raise ValueError(f"invalid component classification: {cls}")
        if action not in actions:
            raise ValueError(f"invalid portability action: {action}")
        if not artifact:
            raise ValueError(f"work item artifact required: {item_id}")
        counts[cls] += 1
        actions[action] += 1
        if action == "REMEDIATE":
            remediation_ids.append(item_id)

    total = len(items)
    return PortabilityMetrics(
        total_work_items=total,
        counts_by_class=dict(sorted(counts.items())),
        reuse_unchanged=actions["REUSE_UNCHANGED"],
        configured=actions["CONFIGURE"],
        remediated=actions["REMEDIATE"],
        manual_remediation_items=tuple(sorted(remediation_ids)),
        reuse_fraction=_ratio(actions["REUSE_UNCHANGED"], total),
        remediation_fraction=_ratio(actions["REMEDIATE"], total),
    )


def execute_portability_pilot(
    *,
    repository_root: str | Path,
    profile: Mapping[str, object],
    onboarding_contract_path: str | Path,
    pipeline_registry_path: str | Path,
) -> PortabilityPilotResult:
    root = Path(repository_root)
    community = profile["community"]
    sources = profile["source_systems"]
    assumptions = profile["onboarding_assumptions"]
    parent_fp = platform_fingerprint(root)
    parent_platform = profile.get("parent_platform") or {}
    version = str(parent_platform.get("version") or "").strip()
    immutable_evidence = str(parent_platform.get("immutable_evidence") or "").strip()
    if version != "0.1.116":
        raise ValueError("pilot parent platform version must be frozen at accepted M10-004 version 0.1.116")
    if not immutable_evidence or not (root / immutable_evidence).is_file():
        raise ValueError("pilot immutable parent evidence is missing")

    onboarding = CommunityOnboardingInput(
        onboarding_id="ONB-RANCHO-VISTOSO-001",
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
    contract = load_onboarding_contract(onboarding_contract_path)
    bootstrap = generate_bootstrap(data=onboarding, contract=contract)

    pipeline_registry = load_pipeline_registry(pipeline_registry_path)
    assert_no_protected_defaults(bootstrap, tuple(str(x) for x in pipeline_registry["protected_defaults"]))

    provenance = profile.get("source_provenance") or {}
    if set(provenance) != {"community_authority", "listing_service", "parcel_authority", "recorder_authority"}:
        raise ValueError("pilot source provenance is incomplete")
    for key, item in provenance.items():
        if not str(item.get("name") or "").strip() or not str(item.get("url") or "").startswith("https://"):
            raise ValueError(f"invalid source provenance: {key}")

    remediations = tuple(profile.get("remediation") or ())
    unresolved = tuple(sorted(
        str(x.get("id")) for x in remediations if str(x.get("status")) != "RESOLVED"
    ))
    if unresolved:
        raise ValueError(f"unresolved portability remediation: {unresolved}")

    for item in remediations:
        artifact = str(item.get("resolution_artifact") or "")
        if not artifact or not (root / artifact).is_file():
            raise ValueError(f"missing remediation resolution artifact: {artifact or item.get('id')}")

    remediation_work_items = {str(x.get("work_item_id")) for x in remediations}
    metrics = _measure(profile)
    if set(metrics.manual_remediation_items) != remediation_work_items:
        raise ValueError("remediation ledger does not exactly cover REMEDIATE work items")

    stage_evidence = profile.get("stage_evidence") or {}
    stage_inputs = {}
    for spec in pipeline_registry["stages"]:
        stage_id = str(spec["id"])
        evidence = stage_evidence.get(stage_id)
        if not isinstance(evidence, dict) or not str(evidence.get("artifact") or "").strip():
            raise ValueError(f"missing pilot evidence for stage: {stage_id}")
        stage_inputs[stage_id] = StageInput(
            stage_id=stage_id,
            checks={
                "pilot_evidence_present": True,
                "remediation_resolved": True,
                "synthetic_data_boundary_preserved": True,
            },
            evidence={
                "artifact": str(evidence["artifact"]),
                "pilot_id": str(profile["pilot_id"]),
                "platform_fingerprint": parent_fp,
            },
        )

    progressive = execute_progressive_pipeline(
        community_id=str(community["community_id"]),
        onboarding_bootstrap_fingerprint=bootstrap.bootstrap_fingerprint,
        stage_inputs=stage_inputs,
        registry=pipeline_registry,
    )
    if progressive.status != "PASS" or not progressive.candidate_fingerprint:
        raise ValueError("M10-004 progressive pilot pipeline did not pass")

    blocking_exceptions = tuple()
    payload = {
        "pilot_id": profile["pilot_id"],
        "community_id": community["community_id"],
        "platform_fingerprint": parent_fp,
        "bootstrap_fingerprint": bootstrap.bootstrap_fingerprint,
        "progressive_candidate_fingerprint": progressive.candidate_fingerprint,
        "metrics": {
            "total_work_items": metrics.total_work_items,
            "counts_by_class": dict(metrics.counts_by_class),
            "reuse_unchanged": metrics.reuse_unchanged,
            "configured": metrics.configured,
            "remediated": metrics.remediated,
            "manual_remediation_items": list(metrics.manual_remediation_items),
            "reuse_fraction": metrics.reuse_fraction,
            "remediation_fraction": metrics.remediation_fraction,
        },
        "unresolved_remediation": list(unresolved),
        "blocking_exceptions": list(blocking_exceptions),
    }
    return PortabilityPilotResult(
        pilot_id=str(profile["pilot_id"]),
        community_id=str(community["community_id"]),
        bootstrap_fingerprint=bootstrap.bootstrap_fingerprint,
        progressive_candidate_fingerprint=progressive.candidate_fingerprint,
        metrics=metrics,
        pilot_fingerprint=_hash(payload),
        unresolved_remediation=unresolved,
        blocking_exceptions=blocking_exceptions,
        status="PASS",
    )
