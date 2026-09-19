from __future__ import annotations
from dataclasses import dataclass
import hashlib, json
from pathlib import Path
from typing import Mapping, Sequence
import yaml

from src.community_temporal_state.cross_system_binding import GovernedInputBundle
from src.community_temporal_state.seller_relevance import ApplicabilitySet
from src.community_temporal_state.unified_seller_intelligence import (
    IntelligenceSourceRef,
    UnifiedIntelligenceItem,
    UnifiedSellerIntelligenceState,
    build_unified_state,
    make_intelligence_item,
    make_source_ref,
)

def _canonical_json(v): return json.dumps(v,sort_keys=True,separators=(",",":"),ensure_ascii=False)
def _hash(v): return hashlib.sha256(_canonical_json(v).encode()).hexdigest()

def load_current_state_registry(path:str|Path)->dict:
    d=yaml.safe_load(Path(path).read_text())
    if d.get("status")!="FROZEN" or d.get("ticket")!="M13-007D":
        raise ValueError("M13-007D current-state registry must be FROZEN")
    return d

@dataclass(frozen=True)
class IntelligenceCandidate:
    candidate_id: str
    dimension: str
    value: object
    source_class: str
    source_artifact_id: str
    source_fingerprint: str
    source_time: str|None
    freshness_state: str
    conflict_state: str
    limitation: str|None

@dataclass(frozen=True)
class CurrentStateBuildResult:
    state: UnifiedSellerIntelligenceState
    applicability_set_fingerprint: str
    input_bundle_fingerprint: str
    excluded_dimensions: tuple[str,...]
    unknown_dimensions: tuple[str,...]
    result_fingerprint: str

def build_current_unified_state(*,intelligence_state_id:str,bundle:GovernedInputBundle,applicability_set:ApplicabilitySet,
    candidates:Sequence[IntelligenceCandidate],a_registry:Mapping[str,object],d_registry:Mapping[str,object],
    policy_version:str,schema_version:str)->CurrentStateBuildResult:
    if bundle.bundle_status!="READY":
        raise ValueError("input bundle must be READY")
    if applicability_set.input_bundle_fingerprint!=bundle.bundle_fingerprint:
        raise ValueError("applicability/input bundle fingerprint mismatch")
    if applicability_set.subject_property_id!=bundle.property_id:
        raise ValueError("applicability property mismatch")
    if applicability_set.community_id!=bundle.community_id:
        raise ValueError("applicability community mismatch")
    if applicability_set.temporal_boundary!=bundle.temporal_boundary:
        raise ValueError("applicability temporal boundary mismatch")

    decisions={x.dimension:x for x in applicability_set.decisions}
    if len(decisions)!=len(applicability_set.decisions):
        raise ValueError("duplicate applicability dimension")
    ordered_candidates=tuple(sorted(candidates,key=lambda x:(x.dimension,x.candidate_id)))
    candidate_dims=[x.dimension for x in ordered_candidates]
    if len(candidate_dims)!=len(set(candidate_dims)):
        raise ValueError("duplicate candidate dimension")

    items=[]
    unknowns=[]
    limitations=[]
    exclusions=[]
    for dimension,decision in sorted(decisions.items()):
        if decision.limitation:
            limitations.append(decision.limitation)
        if decision.applicability_state=="BLOCKED":
            raise ValueError("blocked applicability decision prevents current-state build")
        if decision.applicability_state=="UNKNOWN":
            unknowns.append(dimension)
            unknowns.extend(decision.unknowns)
            continue
        if decision.applicability_state=="NOT_APPLICABLE":
            exclusions.append(dimension)
            continue
        if decision.applicability_state!="APPLICABLE":
            raise ValueError("unsupported applicability state")
        matches=[x for x in ordered_candidates if x.dimension==dimension]
        if len(matches)!=1:
            raise ValueError("applicable dimension requires exactly one intelligence candidate")
        c=matches[0]
        ref=make_source_ref(source_class=c.source_class,source_artifact_id=c.source_artifact_id,
            source_fingerprint=c.source_fingerprint,source_time=c.source_time,registry=a_registry)
        item=make_intelligence_item(item_id=c.candidate_id,dimension=c.dimension,value=c.value,source_class=c.source_class,
            freshness_state=c.freshness_state,conflict_state=c.conflict_state,change_state="UNCHANGED",
            significance_class="INFORMATIONAL",evidence_refs=(ref,),registry=a_registry,limitation=c.limitation)
        items.append(item)
        if c.limitation:
            limitations.append(c.limitation)

    extra={x.dimension for x in ordered_candidates}-set(decisions)
    if extra:
        raise ValueError("candidate exists without governed applicability decision")

    state=build_unified_state(intelligence_state_id=intelligence_state_id,property_id=bundle.property_id,
        community_id=bundle.community_id,temporal_boundary=bundle.temporal_boundary,items=tuple(items),
        unknowns=tuple(sorted(set(unknowns))),limitations=tuple(sorted(set(limitations))),
        stale_dependencies=bundle.stale_systems,policy_version=policy_version,schema_version=schema_version,
        prior_state_fingerprint=None)
    payload={"state_fingerprint":state.state_fingerprint,"applicability_set_fingerprint":applicability_set.set_fingerprint,
      "input_bundle_fingerprint":bundle.bundle_fingerprint,"excluded_dimensions":tuple(sorted(set(exclusions))),
      "unknown_dimensions":tuple(sorted(set(unknowns)))}
    return CurrentStateBuildResult(state=state,applicability_set_fingerprint=applicability_set.set_fingerprint,
      input_bundle_fingerprint=bundle.bundle_fingerprint,excluded_dimensions=payload["excluded_dimensions"],
      unknown_dimensions=payload["unknown_dimensions"],result_fingerprint=_hash(payload))

def validate_current_state_result_replay(result:CurrentStateBuildResult,**kwargs)->bool:
    return build_current_unified_state(**kwargs)==result
