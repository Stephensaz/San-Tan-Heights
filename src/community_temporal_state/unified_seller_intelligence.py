from __future__ import annotations
from dataclasses import asdict, dataclass
import hashlib, json
from pathlib import Path
from typing import Mapping, Sequence
import yaml

def _canonical_json(v: object) -> str:
    return json.dumps(v, sort_keys=True, separators=(",", ":"), ensure_ascii=False)

def _hash(v: object) -> str:
    return hashlib.sha256(_canonical_json(v).encode()).hexdigest()

def _validate_fp(v: str, label: str) -> None:
    if len(v)!=64 or any(c not in "0123456789abcdef" for c in v):
        raise ValueError(f"{label} must be lowercase sha256")

def load_unified_intelligence_registry(path: str|Path) -> dict:
    d=yaml.safe_load(Path(path).read_text())
    if d.get("status")!="FROZEN" or d.get("ticket")!="M13-007A":
        raise ValueError("M13-007A unified intelligence registry must be FROZEN")
    if d.get("unified_intelligence_registry_id")!="STH-M13-007A-UNIFIED-INTELLIGENCE-v1.0":
        raise ValueError("unexpected M13-007A registry id")
    return d

@dataclass(frozen=True)
class IntelligenceSourceRef:
    source_class: str
    source_artifact_id: str
    source_fingerprint: str
    source_time: str|None
    source_ref_fingerprint: str

@dataclass(frozen=True)
class UnifiedIntelligenceItem:
    item_id: str
    dimension: str
    value: object
    source_class: str
    freshness_state: str
    conflict_state: str
    change_state: str
    significance_class: str
    evidence_refs: tuple[IntelligenceSourceRef,...]
    limitation: str|None
    item_fingerprint: str

@dataclass(frozen=True)
class UnifiedSellerIntelligenceState:
    intelligence_state_id: str
    property_id: str
    community_id: str
    temporal_boundary: str
    prior_state_fingerprint: str|None
    items: tuple[UnifiedIntelligenceItem,...]
    unknowns: tuple[str,...]
    limitations: tuple[str,...]
    stale_dependencies: tuple[str,...]
    policy_version: str
    schema_version: str
    state_fingerprint: str

def make_source_ref(*,source_class:str,source_artifact_id:str,source_fingerprint:str,source_time:str|None,registry:Mapping[str,object])->IntelligenceSourceRef:
    if source_class not in set(registry["source_classes"]):
        raise ValueError("unsupported source class")
    if not source_artifact_id.strip():
        raise ValueError("source artifact id required")
    _validate_fp(source_fingerprint,"source fingerprint")
    payload={"source_class":source_class,"source_artifact_id":source_artifact_id,"source_fingerprint":source_fingerprint,"source_time":source_time}
    return IntelligenceSourceRef(**payload,source_ref_fingerprint=_hash(payload))

def make_intelligence_item(*,item_id:str,dimension:str,value:object,source_class:str,freshness_state:str,conflict_state:str,change_state:str,
    significance_class:str,evidence_refs:Sequence[IntelligenceSourceRef],registry:Mapping[str,object],limitation:str|None=None)->UnifiedIntelligenceItem:
    if not item_id.strip() or not dimension.strip():
        raise ValueError("item id and dimension required")
    for field,val,key in (
        ("source class",source_class,"source_classes"),
        ("freshness state",freshness_state,"freshness_states"),
        ("conflict state",conflict_state,"conflict_states"),
        ("change state",change_state,"change_states"),
        ("significance class",significance_class,"significance_classes"),
    ):
        if val not in set(registry[key]): raise ValueError(f"unsupported {field}")
    refs=tuple(sorted(evidence_refs,key=lambda x:(x.source_class,x.source_artifact_id,x.source_fingerprint)))
    if source_class not in {"UNKNOWN","LIMITATION"} and not refs:
        raise ValueError("material intelligence item requires evidence lineage")
    if source_class=="UNKNOWN" and value not in (None,"UNKNOWN"):
        raise ValueError("UNKNOWN source class cannot carry inferred value")
    if conflict_state=="UNRESOLVED_CONFLICT" and significance_class not in {"REVIEW_REQUIRED","INSUFFICIENT_INFORMATION"}:
        raise ValueError("unresolved conflict requires review or insufficient-information significance")
    if freshness_state=="STALE" and change_state!="STALE":
        raise ValueError("stale freshness must remain explicit in change state")
    payload={"item_id":item_id,"dimension":dimension,"value":value,"source_class":source_class,"freshness_state":freshness_state,
      "conflict_state":conflict_state,"change_state":change_state,"significance_class":significance_class,
      "evidence_refs":tuple(asdict(x) for x in refs),"limitation":limitation}
    return UnifiedIntelligenceItem(**{**payload,"evidence_refs":refs},item_fingerprint=_hash(payload))

def build_unified_state(*,intelligence_state_id:str,property_id:str,community_id:str,temporal_boundary:str,items:Sequence[UnifiedIntelligenceItem],
    unknowns:Sequence[str],limitations:Sequence[str],stale_dependencies:Sequence[str],policy_version:str,schema_version:str,
    prior_state_fingerprint:str|None=None)->UnifiedSellerIntelligenceState:
    if not all(x.strip() for x in (intelligence_state_id,property_id,community_id,temporal_boundary,policy_version,schema_version)):
        raise ValueError("state identity fields required")
    if prior_state_fingerprint is not None: _validate_fp(prior_state_fingerprint,"prior state fingerprint")
    ordered=tuple(sorted(items,key=lambda x:x.item_id))
    ids=[x.item_id for x in ordered]
    if len(ids)!=len(set(ids)): raise ValueError("duplicate intelligence item id")
    payload={"intelligence_state_id":intelligence_state_id,"property_id":property_id,"community_id":community_id,
      "temporal_boundary":temporal_boundary,"prior_state_fingerprint":prior_state_fingerprint,
      "items":tuple(asdict(x) for x in ordered),"unknowns":tuple(sorted(set(unknowns))),
      "limitations":tuple(sorted(set(limitations))),"stale_dependencies":tuple(sorted(set(stale_dependencies))),
      "policy_version":policy_version,"schema_version":schema_version}
    return UnifiedSellerIntelligenceState(**{**payload,"items":ordered},state_fingerprint=_hash(payload))

def validate_unified_state_replay(state:UnifiedSellerIntelligenceState,**kwargs)->bool:
    return build_unified_state(**kwargs)==state
