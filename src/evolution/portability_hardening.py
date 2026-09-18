from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
from typing import Mapping

from src.evolution.portability_pilot import execute_portability_pilot
from src.evolution.portability_profiles import validate_disposition_artifacts


def _hash(payload: object) -> str:
    raw=json.dumps(payload,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode("utf-8")
    return sha256(raw).hexdigest()


@dataclass(frozen=True)
class HardeningReplayResult:
    status: str
    prior_manual_remediation: int
    post_manual_remediation: int
    reduction: int
    prior_remediation_fraction: str
    post_remediation_fraction: str
    retained_classifications: Mapping[str,str]
    profile_fingerprints: Mapping[str,str]
    progressive_candidate_fingerprint: str
    replay_fingerprint: str


def _baseline_fingerprint(path: str|Path) -> str:
    return sha256(Path(path).read_bytes()).hexdigest()


def execute_hardened_replay(
    *,
    repository_root: str|Path,
    original_profile: Mapping[str,object],
    hardening_registry: Mapping[str,object],
    onboarding_contract_path: str|Path,
    pipeline_registry_path: str|Path,
    san_tan_baseline_path: str|Path,
    expected_san_tan_baseline_fingerprint: str,
) -> HardeningReplayResult:
    root=Path(repository_root)
    if _baseline_fingerprint(san_tan_baseline_path)!=expected_san_tan_baseline_fingerprint:
        raise ValueError("San Tan Heights accepted baseline changed before M10-006 replay")

    profiles=validate_disposition_artifacts(repository_root=root,registry=hardening_registry)
    prior_remediation=tuple(original_profile.get("remediation") or ())
    prior_ids={str(x.get("work_item_id")) for x in prior_remediation}
    disposition_rows=tuple(hardening_registry.get("dispositions") or ())
    disposition_ids={str(x.get("work_item_id")) for x in disposition_rows}
    if prior_ids!=disposition_ids:
        raise ValueError("M10-006 dispositions must exactly cover M10-005 remediation ledger")

    hardened=deepcopy(original_profile)
    retained={}
    for row in disposition_rows:
        item_id=str(row["work_item_id"])
        matches=[x for x in hardened["work_items"] if str(x.get("id"))==item_id]
        if len(matches)!=1:
            raise ValueError(f"hardening work item missing or duplicated: {item_id}")
        item=matches[0]
        if item.get("component_class")!=row.get("prior_class"):
            raise ValueError(f"hardening may not change classification: {item_id}")
        if item.get("action")!=row.get("prior_action"):
            raise ValueError(f"unexpected prior action: {item_id}")
        item["action"]=row["post_action"]
        item["artifact"]=row["hardened_artifact"]
        retained[item_id]=str(item["component_class"])

    hardened["remediation"]=[]
    replay=execute_portability_pilot(
        repository_root=root,
        profile=hardened,
        onboarding_contract_path=onboarding_contract_path,
        pipeline_registry_path=pipeline_registry_path,
    )
    if replay.status!="PASS":
        raise ValueError("hardened Rancho Vistoso replay failed")
    if replay.metrics.remediated!=0 or replay.metrics.manual_remediation_items:
        raise ValueError("manual remediation remains after hardened profile conversion")

    prior_count=len(prior_ids)
    post_count=replay.metrics.remediated
    fingerprints={k:v.fingerprint for k,v in sorted(profiles.items())}
    payload={
        "pilot_id":original_profile["pilot_id"],
        "prior_manual_remediation":prior_count,
        "post_manual_remediation":post_count,
        "retained_classifications":dict(sorted(retained.items())),
        "profile_fingerprints":fingerprints,
        "progressive_candidate_fingerprint":replay.progressive_candidate_fingerprint,
    }
    return HardeningReplayResult(
        status="PASS",
        prior_manual_remediation=prior_count,
        post_manual_remediation=post_count,
        reduction=prior_count-post_count,
        prior_remediation_fraction=f"{prior_count}/{len(original_profile['work_items'])}",
        post_remediation_fraction=f"{post_count}/{len(original_profile['work_items'])}",
        retained_classifications=dict(sorted(retained.items())),
        profile_fingerprints=fingerprints,
        progressive_candidate_fingerprint=replay.progressive_candidate_fingerprint,
        replay_fingerprint=_hash(payload),
    )
