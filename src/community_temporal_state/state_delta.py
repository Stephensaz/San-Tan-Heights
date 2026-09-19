from __future__ import annotations
from dataclasses import asdict, dataclass
from datetime import datetime
import hashlib, json
from pathlib import Path
from typing import Mapping, Sequence
import yaml

from src.community_temporal_state.unified_seller_intelligence import UnifiedSellerIntelligenceState

def _canonical_json(v): return json.dumps(v,sort_keys=True,separators=(",",":"),ensure_ascii=False)
def _hash(v): return hashlib.sha256(_canonical_json(v).encode()).hexdigest()
def _dt(v):
    try: return datetime.fromisoformat(v)
    except Exception as exc: raise ValueError("temporal boundary must be ISO-8601") from exc

def load_state_delta_registry(path:str|Path)->dict:
    d=yaml.safe_load(Path(path).read_text())
    if d.get("status")!="FROZEN" or d.get("ticket")!="M13-007E":
        raise ValueError("M13-007E state-delta registry must be FROZEN")
    return d

@dataclass(frozen=True)
class SignificanceRule:
    rule_id: str
    dimension: str
    change_state: str
    significance_class: str
    reason: str
    rule_fingerprint: str

@dataclass(frozen=True)
class IntelligenceDelta:
    dimension: str
    change_state: str
    significance_class: str
    significance_rule_id: str
    significance_reason: str
    prior_item_fingerprint: str|None
    current_item_fingerprint: str|None
    prior_value: object
    current_value: object
    prior_unknown: bool
    current_unknown: bool
    delta_fingerprint: str

@dataclass(frozen=True)
class SellerIntelligenceChangeLedger:
    ledger_id: str
    property_id: str
    community_id: str
    prior_state_fingerprint: str
    current_state_fingerprint: str
    prior_temporal_boundary: str
    current_temporal_boundary: str
    deltas: tuple[IntelligenceDelta,...]
    policy_version: str
    ledger_fingerprint: str

def make_significance_rule(*,rule_id:str,dimension:str,change_state:str,significance_class:str,reason:str,registry:Mapping[str,object])->SignificanceRule:
    if not all(x.strip() for x in (rule_id,dimension,change_state,significance_class,reason)):
        raise ValueError("significance rule fields required")
    if change_state not in set(registry["change_states"]): raise ValueError("unsupported change state")
    if significance_class not in set(registry["significance_classes"]): raise ValueError("unsupported significance class")
    payload={"rule_id":rule_id,"dimension":dimension,"change_state":change_state,"significance_class":significance_class,"reason":reason}
    return SignificanceRule(**payload,rule_fingerprint=_hash(payload))

def _classify_dimension(*,dimension,prior_item,current_item,prior_unknown,current_unknown):
    if current_unknown:
        return "UNKNOWN"
    if prior_unknown and current_item is not None:
        return "RESOLVED"
    if prior_item is None and current_item is not None:
        return "NEW"
    if prior_item is not None and current_item is None:
        return "NO_LONGER_APPLICABLE"
    if prior_item is None and current_item is None:
        return "UNKNOWN"
    if current_item.freshness_state=="STALE":
        return "STALE"
    if prior_item.item_fingerprint==current_item.item_fingerprint:
        return "UNCHANGED"
    return "CHANGED"

def build_change_ledger(*,ledger_id:str,prior_state:UnifiedSellerIntelligenceState,current_state:UnifiedSellerIntelligenceState,
    significance_rules:Sequence[SignificanceRule],registry:Mapping[str,object],policy_version:str)->SellerIntelligenceChangeLedger:
    if prior_state.property_id!=current_state.property_id: raise ValueError("property mismatch")
    if prior_state.community_id!=current_state.community_id: raise ValueError("community mismatch")
    if _dt(prior_state.temporal_boundary)>=_dt(current_state.temporal_boundary): raise ValueError("prior temporal boundary must precede current")
    if not ledger_id.strip() or not policy_version.strip(): raise ValueError("ledger identity fields required")
    pitems={x.dimension:x for x in prior_state.items}
    citems={x.dimension:x for x in current_state.items}
    if len(pitems)!=len(prior_state.items) or len(citems)!=len(current_state.items):
        raise ValueError("duplicate intelligence dimension")
    punknown=set(prior_state.unknowns); cunknown=set(current_state.unknowns)
    dimensions=sorted(set(pitems)|set(citems)|punknown|cunknown)
    rules={(x.dimension,x.change_state):x for x in significance_rules}
    if len(rules)!=len(significance_rules): raise ValueError("duplicate significance rule")
    deltas=[]
    for dim in dimensions:
        pi=pitems.get(dim); ci=citems.get(dim)
        change=_classify_dimension(dimension=dim,prior_item=pi,current_item=ci,prior_unknown=dim in punknown,current_unknown=dim in cunknown)
        rule=rules.get((dim,change))
        if rule is None:
            raise ValueError(f"explicit significance rule required for {dim}:{change}")
        payload={"dimension":dim,"change_state":change,"significance_class":rule.significance_class,
          "significance_rule_id":rule.rule_id,"significance_reason":rule.reason,
          "prior_item_fingerprint":pi.item_fingerprint if pi else None,
          "current_item_fingerprint":ci.item_fingerprint if ci else None,
          "prior_value":pi.value if pi else None,"current_value":ci.value if ci else None,
          "prior_unknown":dim in punknown,"current_unknown":dim in cunknown}
        deltas.append(IntelligenceDelta(**payload,delta_fingerprint=_hash(payload)))
    payload={"ledger_id":ledger_id,"property_id":current_state.property_id,"community_id":current_state.community_id,
      "prior_state_fingerprint":prior_state.state_fingerprint,"current_state_fingerprint":current_state.state_fingerprint,
      "prior_temporal_boundary":prior_state.temporal_boundary,"current_temporal_boundary":current_state.temporal_boundary,
      "deltas":tuple(asdict(x) for x in deltas),"policy_version":policy_version}
    return SellerIntelligenceChangeLedger(**{**payload,"deltas":tuple(deltas)},ledger_fingerprint=_hash(payload))

def validate_change_ledger_replay(value:SellerIntelligenceChangeLedger,**kwargs)->bool:
    return build_change_ledger(**kwargs)==value
