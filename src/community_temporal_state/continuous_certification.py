from __future__ import annotations
from dataclasses import asdict, dataclass
import hashlib, json
from pathlib import Path
from typing import Mapping, Sequence
import yaml

def _canonical_json(v): return json.dumps(v,sort_keys=True,separators=(",",":"),ensure_ascii=False)
def _hash(v): return hashlib.sha256(_canonical_json(v).encode()).hexdigest()
def _validate_fp(v:str,label:str)->None:
    if len(v)!=64 or any(c not in "0123456789abcdef" for c in v):
        raise ValueError(f"{label} must be lowercase sha256")

def load_continuous_certification_registry(path:str|Path)->dict:
    d=yaml.safe_load(Path(path).read_text())
    if d.get("status")!="FROZEN" or d.get("ticket")!="M13-009":
        raise ValueError("M13-009 continuous certification registry must be FROZEN")
    return d

@dataclass(frozen=True)
class CertificationArtifact:
    artifact_kind: str
    artifact_id: str
    artifact_fingerprint: str
    artifact_state: str
    lineage_fingerprint: str
    reason: str|None
    artifact_receipt_fingerprint: str

@dataclass(frozen=True)
class ContinuousCertificationReceipt:
    receipt_id: str
    property_id: str
    community_id: str
    temporal_boundary: str
    prior_receipt_fingerprint: str|None
    artifacts: tuple[CertificationArtifact,...]
    certification_state: str
    review_required_artifacts: tuple[str,...]
    blocking_artifacts: tuple[str,...]
    drift_detected: bool
    policy_version: str
    receipt_fingerprint: str

def make_certification_artifact(*,artifact_kind:str,artifact_id:str,artifact_fingerprint:str,
    artifact_state:str,lineage_fingerprint:str,reason:str|None,registry:Mapping[str,object])->CertificationArtifact:
    if not artifact_kind.strip() or not artifact_id.strip(): raise ValueError("artifact kind and id required")
    _validate_fp(artifact_fingerprint,"artifact fingerprint")
    _validate_fp(lineage_fingerprint,"lineage fingerprint")
    allowed={"CERTIFIED","DEGRADED","BLOCKED","STALE","MISSING"}
    if artifact_state not in allowed: raise ValueError("unsupported artifact state")
    if artifact_state!="CERTIFIED" and not (reason and reason.strip()):
        raise ValueError("non-certified artifact state requires explicit reason")
    payload={"artifact_kind":artifact_kind,"artifact_id":artifact_id,"artifact_fingerprint":artifact_fingerprint,
      "artifact_state":artifact_state,"lineage_fingerprint":lineage_fingerprint,"reason":reason}
    return CertificationArtifact(**payload,artifact_receipt_fingerprint=_hash(payload))

def certify_intelligence_cycle(*,receipt_id:str,property_id:str,community_id:str,temporal_boundary:str,
    artifacts:Sequence[CertificationArtifact],registry:Mapping[str,object],policy_version:str,
    prior_receipt_fingerprint:str|None=None,drift_detected:bool=False)->ContinuousCertificationReceipt:
    if not all(x.strip() for x in (receipt_id,property_id,community_id,temporal_boundary,policy_version)):
        raise ValueError("certification identity fields required")
    if prior_receipt_fingerprint is not None: _validate_fp(prior_receipt_fingerprint,"prior receipt fingerprint")
    ordered=tuple(sorted(artifacts,key=lambda x:(x.artifact_kind,x.artifact_id)))
    kinds=[x.artifact_kind for x in ordered]
    if len(kinds)!=len(set(kinds)): raise ValueError("duplicate artifact kind")
    required=tuple(registry["required_artifact_kinds"])
    unknown=set(kinds)-set(required)
    if unknown: raise ValueError("unsupported certification artifact kind")
    missing=sorted(set(required)-set(kinds))
    review_states=set(registry["review_artifact_states"])
    blocking_states=set(registry["blocking_artifact_states"])
    review=[x.artifact_kind for x in ordered if x.artifact_state in review_states]
    blocked=[x.artifact_kind for x in ordered if x.artifact_state in blocking_states]
    blocked.extend(missing)
    if blocked:
        state="BLOCKED"
    elif review or drift_detected:
        state="REVIEW_REQUIRED"
    else:
        state="CERTIFIED"
    payload={"receipt_id":receipt_id,"property_id":property_id,"community_id":community_id,
      "temporal_boundary":temporal_boundary,"prior_receipt_fingerprint":prior_receipt_fingerprint,
      "artifacts":tuple(asdict(x) for x in ordered),"certification_state":state,
      "review_required_artifacts":tuple(sorted(set(review))),"blocking_artifacts":tuple(sorted(set(blocked))),
      "drift_detected":bool(drift_detected),"policy_version":policy_version}
    return ContinuousCertificationReceipt(**{**payload,"artifacts":ordered},receipt_fingerprint=_hash(payload))

def validate_continuous_certification_replay(value:ContinuousCertificationReceipt,**kwargs)->bool:
    return certify_intelligence_cycle(**kwargs)==value
