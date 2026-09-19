from __future__ import annotations
from dataclasses import asdict, dataclass
import hashlib, json
from pathlib import Path
from typing import Mapping
import yaml

from src.community_temporal_state.state_delta import SellerIntelligenceChangeLedger
from src.community_temporal_state.unified_seller_intelligence import UnifiedSellerIntelligenceState

def _canonical_json(v): return json.dumps(v,sort_keys=True,separators=(",",":"),ensure_ascii=False)
def _hash(v): return hashlib.sha256(_canonical_json(v).encode()).hexdigest()

def load_usability_registry(path:str|Path)->dict:
    d=yaml.safe_load(Path(path).read_text())
    if d.get("status")!="FROZEN" or d.get("ticket")!="M13-007F":
        raise ValueError("M13-007F usability registry must be FROZEN")
    return d

@dataclass(frozen=True)
class DimensionUsability:
    dimension: str
    usability_state: str
    reasons: tuple[str,...]
    current_item_fingerprint: str|None
    delta_fingerprint: str
    limitations: tuple[str,...]
    assessment_fingerprint: str

@dataclass(frozen=True)
class IntelligenceUsabilityFramework:
    framework_id: str
    property_id: str
    community_id: str
    current_state_fingerprint: str
    change_ledger_fingerprint: str
    assessments: tuple[DimensionUsability,...]
    stale_dependencies: tuple[str,...]
    framework_status: str
    policy_version: str
    framework_fingerprint: str

def assess_intelligence_usability(*,framework_id:str,current_state:UnifiedSellerIntelligenceState,
    change_ledger:SellerIntelligenceChangeLedger,registry:Mapping[str,object],policy_version:str)->IntelligenceUsabilityFramework:
    if not framework_id.strip() or not policy_version.strip():
        raise ValueError("framework identity fields required")
    if change_ledger.current_state_fingerprint!=current_state.state_fingerprint:
        raise ValueError("change ledger/current state fingerprint mismatch")
    if change_ledger.property_id!=current_state.property_id:
        raise ValueError("property mismatch")
    if change_ledger.community_id!=current_state.community_id:
        raise ValueError("community mismatch")

    items={x.dimension:x for x in current_state.items}
    if len(items)!=len(current_state.items):
        raise ValueError("duplicate current-state dimension")
    deltas={x.dimension:x for x in change_ledger.deltas}
    if len(deltas)!=len(change_ledger.deltas):
        raise ValueError("duplicate delta dimension")
    dimensions=sorted(set(items)|set(current_state.unknowns))
    if set(dimensions)!=set(deltas):
        raise ValueError("current-state dimensions must exactly match change-ledger dimensions")

    assessments=[]
    blocking=set(registry["blocking_conflict_states"])
    review_changes=set(registry["review_change_states"])
    review_significance=set(registry["review_significance_classes"])
    limited_significance=set(registry["limited_significance_classes"])
    for dim in dimensions:
        item=items.get(dim)
        delta=deltas[dim]
        reasons=[]
        limitations=[]
        if dim in current_state.unknowns:
            state="UNKNOWN"
            reasons.append("Current intelligence for this dimension is explicitly unknown.")
        elif item is None:
            raise ValueError("known dimension requires current intelligence item")
        elif item.conflict_state in blocking:
            state="BLOCKED"
            reasons.append("Unresolved evidence conflict blocks this dimension.")
        elif item.freshness_state=="STALE" or delta.change_state in review_changes:
            state="REVIEW_REQUIRED"
            reasons.append("Stale evidence requires review before downstream use.")
        elif delta.significance_class in review_significance:
            state="REVIEW_REQUIRED"
            reasons.append("Governed significance requires human review.")
        elif item.limitation or delta.significance_class in limited_significance:
            state="USABLE_WITH_LIMITATION"
            reasons.append("Intelligence remains usable only with explicit limitation context.")
        else:
            state="USABLE"
            reasons.append("No blocking conflict, stale state, unknown, or limiting condition applies.")

        if item and item.limitation:
            limitations.append(item.limitation)
        limitations.extend(current_state.limitations)
        payload={"dimension":dim,"usability_state":state,"reasons":tuple(sorted(set(reasons))),
          "current_item_fingerprint":item.item_fingerprint if item else None,
          "delta_fingerprint":delta.delta_fingerprint,"limitations":tuple(sorted(set(limitations)))}
        assessments.append(DimensionUsability(**payload,assessment_fingerprint=_hash(payload)))

    ordered=tuple(sorted(assessments,key=lambda x:x.dimension))
    states={x.usability_state for x in ordered}
    if "BLOCKED" in states: framework_status="PARTIALLY_BLOCKED"
    elif "REVIEW_REQUIRED" in states or current_state.stale_dependencies: framework_status="REVIEW_REQUIRED"
    elif "UNKNOWN" in states or "USABLE_WITH_LIMITATION" in states: framework_status="LIMITED"
    else: framework_status="READY"
    payload={"framework_id":framework_id,"property_id":current_state.property_id,"community_id":current_state.community_id,
      "current_state_fingerprint":current_state.state_fingerprint,"change_ledger_fingerprint":change_ledger.ledger_fingerprint,
      "assessments":tuple(asdict(x) for x in ordered),"stale_dependencies":tuple(sorted(set(current_state.stale_dependencies))),
      "framework_status":framework_status,"policy_version":policy_version}
    return IntelligenceUsabilityFramework(**{**payload,"assessments":ordered},framework_fingerprint=_hash(payload))

def validate_usability_replay(value:IntelligenceUsabilityFramework,**kwargs)->bool:
    return assess_intelligence_usability(**kwargs)==value
