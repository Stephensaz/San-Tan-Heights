from __future__ import annotations
from dataclasses import asdict, dataclass
from datetime import datetime
import hashlib, json
from pathlib import Path
from typing import Mapping, Sequence
import yaml

def _canonical_json(v): return json.dumps(v,sort_keys=True,separators=(",",":"),ensure_ascii=False)
def _hash(v): return hashlib.sha256(_canonical_json(v).encode()).hexdigest()
def _fp(v,label):
    if not isinstance(v,str) or len(v)!=64 or any(c not in "0123456789abcdef" for c in v):
        raise ValueError(f"{label} must be lowercase sha256")
def _dt(v):
    try: return datetime.fromisoformat(v)
    except Exception as exc: raise ValueError("temporal boundary must be ISO-8601") from exc

def load_cross_system_binding_registry(path:str|Path)->dict:
    d=yaml.safe_load(Path(path).read_text())
    if d.get("status")!="FROZEN" or d.get("ticket")!="M13-007B": raise ValueError("M13-007B registry must be FROZEN")
    return d

@dataclass(frozen=True)
class DependencyArtifact:
    system_id: str
    artifact_id: str
    property_id: str
    community_id: str
    as_of: str
    artifact_fingerprint: str
    status: str
    limitation: str|None
    dependency_fingerprint: str

@dataclass(frozen=True)
class GovernedInputBundle:
    bundle_id: str
    property_id: str
    community_id: str
    temporal_boundary: str
    dependencies: tuple[DependencyArtifact,...]
    missing_systems: tuple[str,...]
    stale_systems: tuple[str,...]
    conflicting_systems: tuple[str,...]
    incompatible_systems: tuple[str,...]
    bundle_status: str
    policy_version: str
    bundle_fingerprint: str

def make_dependency(*,system_id:str,artifact_id:str,property_id:str,community_id:str,as_of:str,artifact_fingerprint:str,status:str,registry:Mapping[str,object],limitation:str|None=None)->DependencyArtifact:
    if system_id not in set(registry["required_systems"]): raise ValueError("unsupported system id")
    if status not in set(registry["dependency_statuses"]): raise ValueError("unsupported dependency status")
    if not all(x.strip() for x in (artifact_id,property_id,community_id,as_of)): raise ValueError("dependency identity fields required")
    _dt(as_of); _fp(artifact_fingerprint,"artifact fingerprint")
    payload={"system_id":system_id,"artifact_id":artifact_id,"property_id":property_id,"community_id":community_id,"as_of":as_of,"artifact_fingerprint":artifact_fingerprint,"status":status,"limitation":limitation}
    return DependencyArtifact(**payload,dependency_fingerprint=_hash(payload))

def resolve_input_bundle(*,bundle_id:str,property_id:str,community_id:str,temporal_boundary:str,dependencies:Sequence[DependencyArtifact],policy_version:str,registry:Mapping[str,object])->GovernedInputBundle:
    if not all(x.strip() for x in (bundle_id,property_id,community_id,temporal_boundary,policy_version)): raise ValueError("bundle identity fields required")
    boundary=_dt(temporal_boundary)
    ordered=tuple(sorted(dependencies,key=lambda x:x.system_id))
    systems=[x.system_id for x in ordered]
    if len(systems)!=len(set(systems)): raise ValueError("duplicate dependency system")
    for dep in ordered:
        if dep.property_id!=property_id: raise ValueError("property identity mismatch")
        if dep.community_id!=community_id: raise ValueError("community identity mismatch")
        if _dt(dep.as_of)>boundary: raise ValueError("dependency temporal boundary is in the future")
        _fp(dep.artifact_fingerprint,"artifact fingerprint")
    required=set(registry["required_systems"])
    present=set(systems)
    missing=tuple(sorted(required-present))
    stale=tuple(sorted(x.system_id for x in ordered if x.status=="STALE"))
    conflicting=tuple(sorted(x.system_id for x in ordered if x.status=="CONFLICTING"))
    incompatible=tuple(sorted(x.system_id for x in ordered if x.status=="INCOMPATIBLE"))
    if conflicting or incompatible: bundle_status="BLOCKED"
    elif missing or stale: bundle_status="INCOMPLETE"
    else: bundle_status="READY"
    payload={"bundle_id":bundle_id,"property_id":property_id,"community_id":community_id,"temporal_boundary":temporal_boundary,
      "dependencies":tuple(asdict(x) for x in ordered),"missing_systems":missing,"stale_systems":stale,
      "conflicting_systems":conflicting,"incompatible_systems":incompatible,"bundle_status":bundle_status,"policy_version":policy_version}
    return GovernedInputBundle(**{**payload,"dependencies":ordered},bundle_fingerprint=_hash(payload))

def validate_input_bundle_replay(bundle:GovernedInputBundle,**kwargs)->bool:
    return resolve_input_bundle(**kwargs)==bundle
