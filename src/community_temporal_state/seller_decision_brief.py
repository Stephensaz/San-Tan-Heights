from __future__ import annotations
from dataclasses import asdict, dataclass
import hashlib, json
from pathlib import Path
from typing import Mapping
import yaml

from src.community_temporal_state.current_unified_state import CurrentStateBuildResult
from src.community_temporal_state.intelligence_usability import IntelligenceUsabilityFramework
from src.community_temporal_state.state_delta import SellerIntelligenceChangeLedger

def _canonical_json(v): return json.dumps(v,sort_keys=True,separators=(",",":"),ensure_ascii=False)
def _hash(v): return hashlib.sha256(_canonical_json(v).encode()).hexdigest()

def load_seller_brief_registry(path:str|Path)->dict:
    d=yaml.safe_load(Path(path).read_text())
    if d.get("status")!="FROZEN" or d.get("ticket")!="M13-007G":
        raise ValueError("M13-007G seller-brief registry must be FROZEN")
    return d

@dataclass(frozen=True)
class SellerBriefDimension:
    dimension: str
    usability_state: str
    change_state: str
    significance_class: str
    current_value: object
    item_fingerprint: str|None
    delta_fingerprint: str
    usability_fingerprint: str
    evidence_source_fingerprints: tuple[str,...]
    limitations: tuple[str,...]
    review_reasons: tuple[str,...]
    dimension_fingerprint: str

@dataclass(frozen=True)
class GovernedSellerDecisionBrief:
    brief_id: str
    property_id: str
    community_id: str
    temporal_boundary: str
    current_state_fingerprint: str
    change_ledger_fingerprint: str
    usability_framework_fingerprint: str
    dimensions: tuple[SellerBriefDimension,...]
    unknowns: tuple[str,...]
    limitations: tuple[str,...]
    exclusions: tuple[str,...]
    review_required_dimensions: tuple[str,...]
    blocked_dimensions: tuple[str,...]
    policy_version: str
    brief_fingerprint: str

def assemble_seller_decision_brief(*,brief_id:str,current_result:CurrentStateBuildResult,
    change_ledger:SellerIntelligenceChangeLedger,usability: IntelligenceUsabilityFramework,
    registry:Mapping[str,object],policy_version:str)->GovernedSellerDecisionBrief:
    if not brief_id.strip() or not policy_version.strip():
        raise ValueError("brief identity fields required")
    state=current_result.state
    if change_ledger.current_state_fingerprint!=state.state_fingerprint:
        raise ValueError("change ledger/current state fingerprint mismatch")
    if usability.current_state_fingerprint!=state.state_fingerprint:
        raise ValueError("usability/current state fingerprint mismatch")
    if usability.change_ledger_fingerprint!=change_ledger.ledger_fingerprint:
        raise ValueError("usability/change ledger fingerprint mismatch")
    if change_ledger.property_id!=state.property_id or usability.property_id!=state.property_id:
        raise ValueError("property mismatch")
    if change_ledger.community_id!=state.community_id or usability.community_id!=state.community_id:
        raise ValueError("community mismatch")

    items={x.dimension:x for x in state.items}
    deltas={x.dimension:x for x in change_ledger.deltas}
    assessments={x.dimension:x for x in usability.assessments}
    dimensions=sorted(set(items)|set(state.unknowns))
    if set(dimensions)!=set(deltas) or set(dimensions)!=set(assessments):
        raise ValueError("brief input dimension coverage mismatch")

    rows=[]
    review=[]
    blocked=[]
    for dim in dimensions:
        item=items.get(dim)
        delta=deltas[dim]
        assessment=assessments[dim]
        if assessment.usability_state=="BLOCKED":
            blocked.append(dim)
        if assessment.usability_state in {"BLOCKED","REVIEW_REQUIRED","UNKNOWN","USABLE_WITH_LIMITATION"}:
            review.append(dim)
        if item:
            source_fps=tuple(sorted(x.source_fingerprint for x in item.evidence_refs))
            current_value=item.value
            item_fp=item.item_fingerprint
        else:
            source_fps=()
            current_value=None
            item_fp=None
        payload={"dimension":dim,"usability_state":assessment.usability_state,"change_state":delta.change_state,
          "significance_class":delta.significance_class,"current_value":current_value,"item_fingerprint":item_fp,
          "delta_fingerprint":delta.delta_fingerprint,"usability_fingerprint":assessment.assessment_fingerprint,
          "evidence_source_fingerprints":source_fps,"limitations":assessment.limitations,
          "review_reasons":assessment.reasons}
        rows.append(SellerBriefDimension(**payload,dimension_fingerprint=_hash(payload)))

    ordered=tuple(sorted(rows,key=lambda x:x.dimension))
    payload={"brief_id":brief_id,"property_id":state.property_id,"community_id":state.community_id,
      "temporal_boundary":state.temporal_boundary,"current_state_fingerprint":state.state_fingerprint,
      "change_ledger_fingerprint":change_ledger.ledger_fingerprint,"usability_framework_fingerprint":usability.framework_fingerprint,
      "dimensions":tuple(asdict(x) for x in ordered),"unknowns":tuple(sorted(set(state.unknowns))),
      "limitations":tuple(sorted(set(state.limitations))),"exclusions":tuple(sorted(set(current_result.excluded_dimensions))),
      "review_required_dimensions":tuple(sorted(set(review))),"blocked_dimensions":tuple(sorted(set(blocked))),
      "policy_version":policy_version}
    return GovernedSellerDecisionBrief(**{**payload,"dimensions":ordered},brief_fingerprint=_hash(payload))

def validate_seller_brief_replay(value:GovernedSellerDecisionBrief,**kwargs)->bool:
    return assemble_seller_decision_brief(**kwargs)==value
