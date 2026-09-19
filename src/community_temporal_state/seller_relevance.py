from __future__ import annotations
from dataclasses import asdict, dataclass
import hashlib, json
from pathlib import Path
from typing import Mapping, Sequence
import yaml
from src.community_temporal_state.cross_system_binding import GovernedInputBundle

def _canonical_json(v): return json.dumps(v,sort_keys=True,separators=(",",":"),ensure_ascii=False)
def _hash(v): return hashlib.sha256(_canonical_json(v).encode()).hexdigest()
def load_seller_relevance_registry(path:str|Path)->dict:
    d=yaml.safe_load(Path(path).read_text())
    if d.get("status")!="FROZEN" or d.get("ticket")!="M13-007C": raise ValueError("M13-007C registry must be FROZEN")
    return d

@dataclass(frozen=True)
class ApplicabilityRule:
    rule_id: str
    dimension: str
    required_systems: tuple[str,...]
    required_property_facts: tuple[tuple[str,object],...]
    rule_fingerprint: str

@dataclass(frozen=True)
class ApplicabilityDecision:
    decision_id: str
    subject_property_id: str
    dimension: str
    applicability_state: str
    rule_id: str
    rule_outcome: str
    reason: str
    source_dependency_fingerprints: tuple[str,...]
    unknowns: tuple[str,...]
    exclusions: tuple[str,...]
    limitation: str|None
    decision_fingerprint: str

@dataclass(frozen=True)
class ApplicabilitySet:
    applicability_set_id: str
    subject_property_id: str
    community_id: str
    temporal_boundary: str
    input_bundle_fingerprint: str
    decisions: tuple[ApplicabilityDecision,...]
    set_fingerprint: str

def make_rule(*,rule_id:str,dimension:str,required_systems:Sequence[str],required_property_facts:Sequence[tuple[str,object]]=())->ApplicabilityRule:
    if not rule_id.strip() or not dimension.strip(): raise ValueError("rule id and dimension required")
    rs=tuple(sorted(set(required_systems)))
    facts=tuple(sorted(required_property_facts,key=lambda x:x[0]))
    payload={"rule_id":rule_id,"dimension":dimension,"required_systems":rs,"required_property_facts":facts}
    return ApplicabilityRule(**payload,rule_fingerprint=_hash(payload))

def evaluate_applicability(*,decision_id:str,bundle:GovernedInputBundle,rule:ApplicabilityRule,property_facts:Mapping[str,object],
    registry:Mapping[str,object],limitation:str|None=None)->ApplicabilityDecision:
    if bundle.bundle_status!="READY": raise ValueError("input bundle must be READY")
    deps={x.system_id:x for x in bundle.dependencies}
    missing=tuple(sorted(s for s in rule.required_systems if s not in deps))
    blocked=tuple(sorted(s for s in rule.required_systems if s in deps and deps[s].status!="BOUND"))
    unknowns=[]
    mismatches=[]
    for key,expected in rule.required_property_facts:
        if key not in property_facts: unknowns.append(key)
        elif property_facts[key]!=expected: mismatches.append(key)
    if blocked:
        state,outcome="BLOCKED","BLOCKED_DEPENDENCY"; reason="Required dependency is not bound."
    elif missing:
        state,outcome="UNKNOWN","INSUFFICIENT_EVIDENCE"; reason="Required dependency is missing."
    elif unknowns:
        state,outcome="UNKNOWN","INSUFFICIENT_EVIDENCE"; reason="Required property evidence is unknown."
    elif mismatches:
        state,outcome="NOT_APPLICABLE","NO_MATCH"; reason="Property does not satisfy the governed applicability rule."
    else:
        state,outcome="APPLICABLE","MATCH"; reason="Property satisfies the governed applicability rule."
    if state not in set(registry["applicability_states"]): raise ValueError("unsupported applicability state")
    if outcome not in set(registry["rule_outcomes"]): raise ValueError("unsupported rule outcome")
    refs=tuple(sorted(deps[s].dependency_fingerprint for s in rule.required_systems if s in deps))
    exclusions=tuple(sorted(mismatches))
    payload={"decision_id":decision_id,"subject_property_id":bundle.property_id,"dimension":rule.dimension,"applicability_state":state,
      "rule_id":rule.rule_id,"rule_outcome":outcome,"reason":reason,"source_dependency_fingerprints":refs,
      "unknowns":tuple(sorted(unknowns)),"exclusions":exclusions,"limitation":limitation}
    return ApplicabilityDecision(**payload,decision_fingerprint=_hash(payload))

def build_applicability_set(*,applicability_set_id:str,bundle:GovernedInputBundle,decisions:Sequence[ApplicabilityDecision])->ApplicabilitySet:
    if bundle.bundle_status!="READY": raise ValueError("input bundle must be READY")
    ordered=tuple(sorted(decisions,key=lambda x:(x.dimension,x.rule_id,x.decision_id)))
    ids=[x.decision_id for x in ordered]
    if len(ids)!=len(set(ids)): raise ValueError("duplicate applicability decision id")
    if any(x.subject_property_id!=bundle.property_id for x in ordered): raise ValueError("decision property mismatch")
    payload={"applicability_set_id":applicability_set_id,"subject_property_id":bundle.property_id,"community_id":bundle.community_id,
      "temporal_boundary":bundle.temporal_boundary,"input_bundle_fingerprint":bundle.bundle_fingerprint,
      "decisions":tuple(asdict(x) for x in ordered)}
    return ApplicabilitySet(**{**payload,"decisions":ordered},set_fingerprint=_hash(payload))

def validate_applicability_set_replay(value:ApplicabilitySet,**kwargs)->bool:
    return build_applicability_set(**kwargs)==value
