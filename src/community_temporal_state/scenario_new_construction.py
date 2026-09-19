from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib, json
from pathlib import Path
from typing import Mapping
import yaml

from src.community_temporal_state.scenario_baseline import CertifiedScenarioBaseline
from src.community_temporal_state.scenario_buyer_substitution import BuyerSubstitutionCompetitiveState


def _canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _hash(value: object) -> str:
    return hashlib.sha256(_canonical_json(value).encode()).hexdigest()


def _validate_fp(value: str, label: str) -> None:
    if len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
        raise ValueError(f"{label} must be lowercase sha256")


def load_new_construction_registry(path: str | Path) -> dict:
    data=yaml.safe_load(Path(path).read_text())
    if data.get("status")!="FROZEN" or data.get("ticket")!="M13-006F":
        raise ValueError("M13-006F new-construction registry must be FROZEN")
    if data.get("new_construction_registry_id")!="STH-M13-006F-NEW-CONSTRUCTION-v1.0":
        raise ValueError("unexpected M13-006F registry id")
    return data


@dataclass(frozen=True)
class NewConstructionNumericPosition:
    dimension: str
    candidate_value: float
    reference_fact_key: str
    reference_value: float
    absolute_difference: float
    direction: str
    position_fingerprint: str


@dataclass(frozen=True)
class NewConstructionCategoricalPosition:
    dimension: str
    candidate_value: str
    reference_fact_key: str
    reference_value: str
    relation: str
    position_fingerprint: str


@dataclass(frozen=True)
class NewConstructionScenarioState:
    scenario_id: str
    scenario_context_fingerprint: str
    buyer_substitution_state_fingerprint: str
    new_construction_competition: NewConstructionNumericPosition | None
    builder_inventory: NewConstructionNumericPosition | None
    builder_incentive_value: NewConstructionNumericPosition | None
    builder_incentive_posture: NewConstructionCategoricalPosition | None
    unknowns: tuple[str, ...]
    limitations: tuple[str, ...]
    state_fingerprint: str


def _first_fact(facts: Mapping[str, object], keys: list[str]):
    for key in keys:
        if key in facts:
            return key, facts[key]
    return None


def _numeric(dimension: str, candidate: object, key: str, reference: object):
    if isinstance(candidate,bool) or not isinstance(candidate,(int,float)) or float(candidate)<0:
        raise ValueError(f"{dimension} candidate must be non-negative numeric")
    if isinstance(reference,bool) or not isinstance(reference,(int,float)) or float(reference)<0:
        raise ValueError(f"{dimension} reference must be non-negative numeric")
    c=float(candidate); r=float(reference); diff=round(c-r,6)
    direction="SAME" if diff==0 else ("ABOVE_REFERENCE" if diff>0 else "BELOW_REFERENCE")
    payload={"dimension":dimension,"candidate_value":c,"reference_fact_key":key,"reference_value":r,"absolute_difference":diff,"direction":direction}
    return NewConstructionNumericPosition(**payload,position_fingerprint=_hash(payload))


def _categorical(dimension: str, candidate: object, key: str, reference: object):
    if not isinstance(candidate,str) or not candidate.strip():
        raise ValueError(f"{dimension} candidate must be non-empty text")
    if not isinstance(reference,str) or not reference.strip():
        raise ValueError(f"{dimension} reference must be non-empty text")
    c=candidate.strip(); r=reference.strip()
    payload={"dimension":dimension,"candidate_value":c,"reference_fact_key":key,"reference_value":r,"relation":"SAME" if c==r else "DIFFERENT"}
    return NewConstructionCategoricalPosition(**payload,position_fingerprint=_hash(payload))


def build_new_construction_scenario_state(
    *,
    context: CertifiedScenarioBaseline,
    buyer_substitution_state: BuyerSubstitutionCompetitiveState,
    registry: Mapping[str, object],
) -> NewConstructionScenarioState:
    _validate_fp(context.context_fingerprint,"scenario context fingerprint")
    _validate_fp(buyer_substitution_state.state_fingerprint,"buyer substitution state fingerprint")
    if buyer_substitution_state.scenario_id!=context.scenario_id:
        raise ValueError("scenario identity mismatch")
    if buyer_substitution_state.scenario_context_fingerprint!=context.context_fingerprint:
        raise ValueError("scenario context/buyer substitution lineage mismatch")

    facts=dict(context.facts); assumptions=dict(context.assumptions)
    unknowns=set(context.unknowns)|set(buyer_substitution_state.unknowns)
    limitations=set(context.limitations)|set(buyer_substitution_state.limitations)
    numeric={}
    for name in ("new_construction_competition","builder_inventory","builder_incentive_value"):
        spec=registry["dimensions"][name]
        if spec["assumption_key"] not in assumptions:
            numeric[name]=None
            unknowns.add(f"EXPLICIT_{name.upper()}_ASSUMPTION_NOT_PROVIDED")
            continue
        ref=_first_fact(facts,list(spec["reference_fact_keys"]))
        if ref is None:
            numeric[name]=None
            unknowns.add(f"CERTIFIED_{name.upper()}_REFERENCE_NOT_AVAILABLE")
            continue
        numeric[name]=_numeric(name,assumptions[spec["assumption_key"]],ref[0],ref[1])

    spec=registry["dimensions"]["builder_incentive_posture"]
    posture=None
    if spec["assumption_key"] not in assumptions:
        unknowns.add("EXPLICIT_BUILDER_INCENTIVE_POSTURE_ASSUMPTION_NOT_PROVIDED")
    else:
        ref=_first_fact(facts,list(spec["reference_fact_keys"]))
        if ref is None:
            unknowns.add("CERTIFIED_BUILDER_INCENTIVE_POSTURE_REFERENCE_NOT_AVAILABLE")
        else:
            posture=_categorical("builder_incentive_posture",assumptions[spec["assumption_key"]],ref[0],ref[1])

    limitations.add("New-construction competition, inventory, and incentive states are descriptive scenario context, not builder-behavior forecasts or strategy recommendations.")
    payload={
        "scenario_id":context.scenario_id,
        "scenario_context_fingerprint":context.context_fingerprint,
        "buyer_substitution_state_fingerprint":buyer_substitution_state.state_fingerprint,
        "new_construction_competition":asdict(numeric["new_construction_competition"]) if numeric["new_construction_competition"] else None,
        "builder_inventory":asdict(numeric["builder_inventory"]) if numeric["builder_inventory"] else None,
        "builder_incentive_value":asdict(numeric["builder_incentive_value"]) if numeric["builder_incentive_value"] else None,
        "builder_incentive_posture":asdict(posture) if posture else None,
        "unknowns":tuple(sorted(unknowns)),
        "limitations":tuple(sorted(limitations)),
    }
    return NewConstructionScenarioState(
        scenario_id=payload["scenario_id"],
        scenario_context_fingerprint=payload["scenario_context_fingerprint"],
        buyer_substitution_state_fingerprint=payload["buyer_substitution_state_fingerprint"],
        new_construction_competition=numeric["new_construction_competition"],
        builder_inventory=numeric["builder_inventory"],
        builder_incentive_value=numeric["builder_incentive_value"],
        builder_incentive_posture=posture,
        unknowns=payload["unknowns"],
        limitations=payload["limitations"],
        state_fingerprint=_hash(payload),
    )


def validate_new_construction_state_replay(state: NewConstructionScenarioState, *, context: CertifiedScenarioBaseline, buyer_substitution_state: BuyerSubstitutionCompetitiveState, registry: Mapping[str, object]) -> bool:
    return build_new_construction_scenario_state(context=context,buyer_substitution_state=buyer_substitution_state,registry=registry)==state
