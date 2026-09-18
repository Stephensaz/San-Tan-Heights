from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from pathlib import Path
from typing import Iterable, Mapping
import yaml

from src.seller_intelligence.strategy import PropertySellerStrategy


def _hash(payload: object) -> str:
    raw=json.dumps(payload,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode("utf-8")
    return sha256(raw).hexdigest()


def _validate_fingerprint(value: str, label: str) -> None:
    if len(value)!=64 or any(c not in "0123456789abcdef" for c in value):
        raise ValueError(f"{label} must be lowercase sha256")


@dataclass(frozen=True)
class ScenarioAssumption:
    assumption_id: str
    subject_property_id: str
    target: str
    hypothetical_state: str
    rationale: str
    hypothetical: bool


@dataclass(frozen=True)
class SensitivityComparison:
    target: str
    baseline_status: str
    baseline_state: str | None
    hypothetical_state: str
    change_type: str
    assumption_id: str
    assumption_fingerprint: str
    comparison_fingerprint: str


@dataclass(frozen=True)
class ScenarioSensitivityResult:
    scenario_id: str
    subject_property_id: str
    baseline_strategy_fingerprint: str
    baseline_lineage_fingerprints: tuple[str,...]
    hypothetical_assumption_fingerprints: tuple[str,...]
    comparisons: tuple[SensitivityComparison,...]
    unchanged_targets: tuple[str,...]
    unmodeled_targets: tuple[str,...]
    hypothetical_only: bool
    disclaimer: str
    output_tier: str
    public_eligible: bool
    external_action_capability: str
    scenario_fingerprint: str


def load_seller_scenario_registry(path: str|Path) -> dict:
    raw=yaml.safe_load(Path(path).read_text())
    if raw.get("seller_scenario_registry_id")!="STH-M11-003-SELLER-SCENARIO-SENSITIVITY-v1.0":
        raise ValueError("unexpected M11-003 seller scenario registry id")
    if str(raw.get("version"))!="1.0.0" or raw.get("status")!="FROZEN":
        raise ValueError("M11-003 registry must be FROZEN v1.0")
    if raw.get("ticket")!="M11-003" or raw.get("parent_ticket")!="M11-002":
        raise ValueError("M11-003 registry lineage mismatch")
    return raw


def _baseline_states(strategy: PropertySellerStrategy) -> dict[str,tuple[str,str|None]]:
    out={
        "COMPETITIVE_PRESSURE":("CURRENT",strategy.competitive_pressure_level),
    }
    for dimension in strategy.dimensions:
        out[dimension.dimension]=(dimension.status,dimension.state)
    for trigger in strategy.review_triggers:
        out[f"REVIEW_DAY_{trigger.day}"]=(
            "CURRENT",
            "TRIGGERED" if trigger.triggered else "NOT_TRIGGERED",
        )
    return out


def _validate_prohibited_fields(result: ScenarioSensitivityResult, registry: Mapping[str,object]) -> None:
    keys=set(asdict(result))
    prohibited=set(str(x) for x in registry["prohibited_output_fields"])
    overlap=keys & prohibited
    if overlap:
        raise ValueError(f"prohibited scenario output fields present: {sorted(overlap)}")


def evaluate_seller_scenario(
    *,
    scenario_id: str,
    strategy: PropertySellerStrategy,
    m11_002_certified: bool,
    m11_002_evidence_fingerprint: str,
    assumptions: Iterable[ScenarioAssumption],
    registry: Mapping[str,object],
) -> ScenarioSensitivityResult:
    scenario_id=str(scenario_id).strip()
    if not scenario_id:
        raise ValueError("scenario_id required")
    if m11_002_certified is not True:
        raise ValueError("certified M11-002 strategy required")
    _validate_fingerprint(m11_002_evidence_fingerprint,"m11_002_evidence_fingerprint")
    if strategy.output_tier!="SELLER" or strategy.public_eligible is not False:
        raise ValueError("M11-002 strategy eligibility boundary violated")
    if strategy.external_action_capability!="NONE":
        raise ValueError("M11-002 strategy external action boundary violated")

    subject=strategy.subject_property_id
    targets=registry["scenario_targets"]
    baseline=_baseline_states(strategy)
    if set(targets)!=set(baseline):
        raise ValueError("scenario target registry does not exactly match M11-002 strategy surface")

    seen_ids=set()
    seen_targets=set()
    comparisons=[]
    assumption_fps=[]
    for assumption in tuple(assumptions):
        if not assumption.assumption_id.strip():
            raise ValueError("assumption_id required")
        if assumption.assumption_id in seen_ids:
            raise ValueError("duplicate assumption_id")
        seen_ids.add(assumption.assumption_id)
        if assumption.subject_property_id!=subject:
            raise ValueError("scenario assumption subject_property_id mismatch")
        if assumption.hypothetical is not True:
            raise ValueError("scenario assumptions must be explicitly hypothetical")
        if assumption.target not in targets:
            raise ValueError("unsupported scenario target")
        if assumption.target in seen_targets:
            raise ValueError("duplicate scenario target")
        seen_targets.add(assumption.target)
        allowed=set(str(x) for x in targets[assumption.target]["allowed_states"])
        if assumption.hypothetical_state not in allowed:
            raise ValueError("unsupported hypothetical scenario state")
        rationale=assumption.rationale.strip()
        if not rationale:
            raise ValueError("hypothetical assumption rationale required")

        assumption_payload={
            "scenario_id":scenario_id,
            "assumption_id":assumption.assumption_id,
            "subject_property_id":subject,
            "target":assumption.target,
            "hypothetical_state":assumption.hypothetical_state,
            "rationale":rationale,
            "hypothetical":True,
        }
        assumption_fp=_hash(assumption_payload)
        assumption_fps.append(assumption_fp)

        baseline_status,baseline_state=baseline[assumption.target]
        if baseline_state is None:
            change_type="HYPOTHETICAL_ONLY"
        elif baseline_state==assumption.hypothetical_state:
            change_type="UNCHANGED"
        else:
            change_type="CHANGED"
        comparison_payload={
            "target":assumption.target,
            "baseline_status":baseline_status,
            "baseline_state":baseline_state,
            "hypothetical_state":assumption.hypothetical_state,
            "change_type":change_type,
            "assumption_id":assumption.assumption_id,
            "assumption_fingerprint":assumption_fp,
        }
        comparisons.append(SensitivityComparison(
            target=assumption.target,
            baseline_status=baseline_status,
            baseline_state=baseline_state,
            hypothetical_state=assumption.hypothetical_state,
            change_type=change_type,
            assumption_id=assumption.assumption_id,
            assumption_fingerprint=assumption_fp,
            comparison_fingerprint=_hash(comparison_payload),
        ))

    comparisons=sorted(comparisons,key=lambda x:x.target)
    assumption_fps_tuple=tuple(sorted(assumption_fps))
    baseline_lineage=tuple(sorted(set(strategy.lineage_fingerprints) | {
        strategy.strategy_fingerprint,
        m11_002_evidence_fingerprint,
    }))
    if set(baseline_lineage) & set(assumption_fps_tuple):
        raise ValueError("baseline and hypothetical lineage collision")

    unchanged=tuple(sorted(x.target for x in comparisons if x.change_type=="UNCHANGED"))
    unmodeled=tuple(sorted(set(targets)-seen_targets))
    disclaimer=(
        "This is a hypothetical sensitivity scenario, not a statement of current fact. "
        "It does not recommend a list price, predict a sale price, guarantee proceeds or outcomes, "
        "predict seller acceptance or buyer behavior, or authorize any external action."
    )
    payload={
        "scenario_id":scenario_id,
        "subject_property_id":subject,
        "baseline_strategy_fingerprint":strategy.strategy_fingerprint,
        "baseline_lineage_fingerprints":baseline_lineage,
        "hypothetical_assumption_fingerprints":assumption_fps_tuple,
        "comparisons":[x.comparison_fingerprint for x in comparisons],
        "unchanged_targets":unchanged,
        "unmodeled_targets":unmodeled,
        "hypothetical_only":True,
        "disclaimer":disclaimer,
        "output_tier":"SELLER",
        "public_eligible":False,
        "external_action_capability":"NONE",
    }
    result=ScenarioSensitivityResult(
        scenario_id=scenario_id,
        subject_property_id=subject,
        baseline_strategy_fingerprint=strategy.strategy_fingerprint,
        baseline_lineage_fingerprints=baseline_lineage,
        hypothetical_assumption_fingerprints=assumption_fps_tuple,
        comparisons=tuple(comparisons),
        unchanged_targets=unchanged,
        unmodeled_targets=unmodeled,
        hypothetical_only=True,
        disclaimer=disclaimer,
        output_tier="SELLER",
        public_eligible=False,
        external_action_capability="NONE",
        scenario_fingerprint=_hash(payload),
    )
    _validate_prohibited_fields(result,registry)
    return result
