from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
from typing import Iterable, Mapping
import re
import yaml

_SHA = re.compile(r"^[0-9a-f]{64}$")


def _hash(payload: object) -> str:
    raw=json.dumps(payload,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode("utf-8")
    return sha256(raw).hexdigest()


@dataclass(frozen=True)
class BaselineIdentity:
    baseline_id: str
    baseline_version: str
    baseline_fingerprint: str
    source_revision: str


@dataclass(frozen=True)
class ChangeRequest:
    change_request_id: str
    change_class: str
    version_class: str
    component_class: str
    parent_baseline_id: str
    parent_baseline_version: str
    parent_baseline_fingerprint: str
    description: str
    emergency: bool
    impact_keys: tuple[str,...]
    request_fingerprint: str


@dataclass(frozen=True)
class CandidateManifest:
    candidate_id: str
    candidate_version: str
    parent_baseline_fingerprint: str
    change_request_fingerprint: str
    changed_artifacts: Mapping[str,str]
    structured_diff: tuple[str,...]
    recertification_scope: tuple[str,...]
    blocking_exceptions: tuple[str,...]
    candidate_fingerprint: str
    promotion_eligible: bool


def load_policy(path: str|Path) -> dict:
    p=yaml.safe_load(Path(path).read_text())
    if p.get("change_control_registry_id")!="STH-M10-001-BASELINE-EVOLUTION-v1.0" or p.get("status")!="FROZEN":
        raise ValueError("invalid frozen M10-001 policy")
    return p


def load_baseline(path: str|Path) -> BaselineIdentity:
    path=Path(path); raw=path.read_bytes(); data=json.loads(raw)
    if data.get("status")!="ACCEPTED_IMMUTABLE" or data.get("immutable") is not True or data.get("in_place_mutation_allowed") is not False:
        raise ValueError("baseline is not immutable/accepted")
    return BaselineIdentity(str(data["baseline_id"]),str(data["baseline_version"]),sha256(raw).hexdigest(),str(data["source_revision"]))


def create_change_request(*, policy: Mapping[str,object], baseline: BaselineIdentity, change_request_id: str,
                          change_class: str, version_class: str, component_class: str, description: str,
                          impact_keys: Iterable[str], emergency: bool=False) -> ChangeRequest:
    classes=policy["change_classes"]
    if change_class not in classes: raise ValueError("unclassified change")
    if component_class not in set(policy["component_classes"]): raise ValueError("unclassified component")
    if version_class not in {"PATCH","MINOR","MAJOR"}: raise ValueError("invalid semantic version class")
    if not change_request_id.strip() or not description.strip(): raise ValueError("change request identity/description required")
    impacts=tuple(sorted(set(str(x) for x in impact_keys if str(x).strip())))
    if not impacts: raise ValueError("impact scope required")
    if emergency and policy["governance"]["emergency_bypass_prohibited"] is not True:
        raise ValueError("emergency governance weakened")
    payload={"change_request_id":change_request_id,"change_class":change_class,"version_class":version_class,
             "component_class":component_class,"parent_baseline_id":baseline.baseline_id,
             "parent_baseline_version":baseline.baseline_version,"parent_baseline_fingerprint":baseline.baseline_fingerprint,
             "description":description,"emergency":emergency,"impact_keys":list(impacts)}
    return ChangeRequest(change_request_id,change_class,version_class,component_class,baseline.baseline_id,
                         baseline.baseline_version,baseline.baseline_fingerprint,description,emergency,impacts,_hash(payload))


def create_candidate(*, policy: Mapping[str,object], baseline: BaselineIdentity, request: ChangeRequest,
                     candidate_id: str, candidate_version: str, changed_artifacts: Mapping[str,str],
                     structured_diff: Iterable[str], blocking_exceptions: Iterable[str]=()) -> CandidateManifest:
    if request.parent_baseline_fingerprint!=baseline.baseline_fingerprint: raise ValueError("parent baseline fingerprint mismatch")
    if candidate_version==baseline.baseline_version: raise ValueError("candidate version must differ from immutable baseline")
    if not candidate_id.strip(): raise ValueError("candidate_id required")
    artifacts=dict(sorted(changed_artifacts.items()))
    if not artifacts: raise ValueError("candidate requires changed artifacts")
    for h in artifacts.values():
        if not _SHA.fullmatch(h): raise ValueError("artifact fingerprint must be sha256")
    diff=tuple(sorted(set(str(x) for x in structured_diff if str(x).strip())))
    if not diff: raise ValueError("structured baseline diff required")
    scopes=tuple(sorted(set(policy["change_classes"][request.change_class]["recertification_scopes"])))
    blockers=tuple(sorted(set(str(x) for x in blocking_exceptions if str(x).strip())))
    payload={"candidate_id":candidate_id,"candidate_version":candidate_version,
             "parent_baseline_fingerprint":baseline.baseline_fingerprint,
             "change_request_fingerprint":request.request_fingerprint,"changed_artifacts":artifacts,
             "structured_diff":list(diff),"recertification_scope":list(scopes)}
    fp=_hash(payload)
    return CandidateManifest(candidate_id,candidate_version,baseline.baseline_fingerprint,request.request_fingerprint,
                             artifacts,diff,scopes,blockers,fp,not blockers)


def verify_baseline_unchanged(*, baseline_path: str|Path, frozen_fingerprint: str) -> None:
    actual=sha256(Path(baseline_path).read_bytes()).hexdigest()
    if actual!=frozen_fingerprint: raise ValueError("accepted baseline mutation detected")


def authorize_promotion(*, candidate: CandidateManifest, required_evidence: Mapping[str,str], policy: Mapping[str,object]) -> str:
    if candidate.blocking_exceptions: raise ValueError("blocking exceptions prevent promotion")
    if not required_evidence: raise ValueError("promotion evidence required")
    if any(v!="PASS" for v in required_evidence.values()): raise ValueError("required promotion evidence has not passed")
    if policy["governance"]["promotion_requires_zero_blocking_exceptions"] is not True: raise ValueError("promotion policy weakened")
    return _hash({"candidate_fingerprint":candidate.candidate_fingerprint,
                  "required_evidence":dict(sorted(required_evidence.items()))})


def rollback_target(*, exact_baseline: BaselineIdentity, requested_fingerprint: str) -> BaselineIdentity:
    if requested_fingerprint!=exact_baseline.baseline_fingerprint:
        raise ValueError("rollback requires exact certified baseline artifact")
    return exact_baseline
