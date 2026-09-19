from __future__ import annotations
from dataclasses import asdict, dataclass, replace
import hashlib, json
from pathlib import Path
from typing import Mapping, Sequence
import yaml
from src.community_temporal_state.scenario_explainability import ScenarioExplanation, ComparisonExplanation

def _canonical_json(v): return json.dumps(v,sort_keys=True,separators=(",",":"),ensure_ascii=False)
def _hash(v): return hashlib.sha256(_canonical_json(v).encode()).hexdigest()
def _valid_fp(v):
    return isinstance(v,str) and len(v)==64 and all(c in "0123456789abcdef" for c in v)

def load_review_workspace_registry(path: str|Path)->dict:
    d=yaml.safe_load(Path(path).read_text())
    if d.get("status")!="FROZEN" or d.get("ticket")!="M13-006I": raise ValueError("M13-006I review workspace registry must be FROZEN")
    return d

@dataclass(frozen=True)
class ScenarioReviewPackage:
    review_package_id: str
    subject_id: str
    community_id: str
    baseline_snapshot_id: str
    temporal_boundary: str
    scenario_ids: tuple[str,...]
    scenario_explanation_fingerprints: tuple[str,...]
    comparison_explanation_fingerprint: str
    facts: tuple[tuple[str,object],...]
    assumptions: tuple[tuple[str,object],...]
    evidence_fingerprints: tuple[str,...]
    unknowns: tuple[str,...]
    limitations: tuple[str,...]
    policy_version: str
    package_status: str
    blocking_conditions: tuple[str,...]
    supersedes_package_fingerprint: str|None
    package_fingerprint: str

@dataclass(frozen=True)
class HumanReviewReceipt:
    review_package_fingerprint: str
    review_state: str
    reviewer_id: str
    note: str|None
    receipt_fingerprint: str

def build_review_package(*,review_package_id:str,subject_id:str,community_id:str,baseline_snapshot_id:str,temporal_boundary:str,
    scenario_explanations:Sequence[ScenarioExplanation],comparison_explanation:ComparisonExplanation,policy_version:str,
    registry:Mapping[str,object],blocking_conditions:Sequence[str]=(),supersedes_package_fingerprint:str|None=None)->ScenarioReviewPackage:
    if not all(x.strip() for x in (review_package_id,subject_id,community_id,baseline_snapshot_id,temporal_boundary,policy_version)): raise ValueError("review identity fields required")
    if not _valid_fp(comparison_explanation.explanation_fingerprint): raise ValueError("comparison explanation fingerprint invalid")
    if supersedes_package_fingerprint is not None and not _valid_fp(supersedes_package_fingerprint): raise ValueError("superseded package fingerprint invalid")
    by_id={x.scenario_id:x for x in scenario_explanations}
    if set(by_id)!=set(comparison_explanation.scenario_ids): raise ValueError("explainability coverage incomplete")
    if tuple(by_id[s].explanation_fingerprint for s in comparison_explanation.scenario_ids)!=comparison_explanation.scenario_explanation_fingerprints:
        raise ValueError("scenario/comparison explanation lineage mismatch")
    for x in scenario_explanations:
        if not _valid_fp(x.explanation_fingerprint): raise ValueError("scenario explanation fingerprint invalid")
    blocks=tuple(sorted(set(blocking_conditions)))
    allowed=set(registry["blocking_conditions"])
    if any(x not in allowed for x in blocks): raise ValueError("unsupported blocking condition")
    status="STALE_REVIEW_REQUIRED" if blocks else "READY_FOR_HUMAN_REVIEW"
    facts=tuple(sorted({item for x in scenario_explanations for item in x.facts},key=lambda z:z[0]))
    assumptions=tuple(sorted({item for x in scenario_explanations for item in x.assumptions},key=lambda z:z[0]))
    evidence=tuple(sorted({fp for x in scenario_explanations for fp in x.evidence_fingerprints}))
    unknowns=tuple(sorted(set(comparison_explanation.unknowns)|{u for x in scenario_explanations for u in x.unknowns}))
    limitations=tuple(sorted(set(comparison_explanation.limitations)|{l for x in scenario_explanations for l in x.limitations}))
    if not limitations: raise ValueError("limitations required")
    payload={"review_package_id":review_package_id,"subject_id":subject_id,"community_id":community_id,"baseline_snapshot_id":baseline_snapshot_id,
      "temporal_boundary":temporal_boundary,"scenario_ids":comparison_explanation.scenario_ids,
      "scenario_explanation_fingerprints":comparison_explanation.scenario_explanation_fingerprints,
      "comparison_explanation_fingerprint":comparison_explanation.explanation_fingerprint,"facts":facts,"assumptions":assumptions,
      "evidence_fingerprints":evidence,"unknowns":unknowns,"limitations":limitations,"policy_version":policy_version,
      "package_status":status,"blocking_conditions":blocks,"supersedes_package_fingerprint":supersedes_package_fingerprint}
    return ScenarioReviewPackage(**payload,package_fingerprint=_hash(payload))

def mark_package_stale(package:ScenarioReviewPackage,*,condition:str,registry:Mapping[str,object])->ScenarioReviewPackage:
    if condition not in set(registry["blocking_conditions"]): raise ValueError("unsupported blocking condition")
    blocks=tuple(sorted(set((*package.blocking_conditions,condition))))
    payload=asdict(package); payload.pop("package_fingerprint"); payload["package_status"]="STALE_REVIEW_REQUIRED"; payload["blocking_conditions"]=blocks
    return replace(package,package_status="STALE_REVIEW_REQUIRED",blocking_conditions=blocks,package_fingerprint=_hash(payload))

def record_human_review(*,package:ScenarioReviewPackage,review_state:str,reviewer_id:str,registry:Mapping[str,object],note:str|None=None)->HumanReviewReceipt:
    if package.package_status!="READY_FOR_HUMAN_REVIEW": raise ValueError("package not ready for review")
    if review_state not in set(registry["review_states"]): raise ValueError("unsupported review state")
    if not reviewer_id.strip(): raise ValueError("reviewer id required")
    payload={"review_package_fingerprint":package.package_fingerprint,"review_state":review_state,"reviewer_id":reviewer_id,"note":note}
    return HumanReviewReceipt(**payload,receipt_fingerprint=_hash(payload))

def validate_review_package_replay(package:ScenarioReviewPackage,**kwargs)->bool:
    return build_review_package(**kwargs)==package
