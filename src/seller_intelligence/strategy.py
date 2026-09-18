from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from pathlib import Path
from typing import Iterable, Mapping
import yaml

from src.seller_intelligence.opportunity import SellerOpportunityResult


def _hash(payload: object) -> str:
    raw=json.dumps(payload,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode("utf-8")
    return sha256(raw).hexdigest()


def _validate_fingerprint(value: str, label: str) -> None:
    if len(value)!=64 or any(c not in "0123456789abcdef" for c in value):
        raise ValueError(f"{label} must be lowercase sha256")


@dataclass(frozen=True)
class GovernedStrategyFinding:
    finding_id: str
    subject_property_id: str
    dimension: str
    state: str
    summary: str
    baseline_certified: bool
    qa_status: str
    output_tier: str
    freshness_state: str
    evidence_fingerprint: str


@dataclass(frozen=True)
class StrategyDimension:
    dimension: str
    status: str
    state: str | None
    summary: str
    evidence_fingerprints: tuple[str,...]
    suppressed_finding_ids: tuple[str,...]
    dimension_fingerprint: str


@dataclass(frozen=True)
class ReviewTrigger:
    day: int
    name: str
    triggered: bool
    reasons: tuple[str,...]
    instruction: str
    trigger_fingerprint: str


@dataclass(frozen=True)
class PropertySellerStrategy:
    subject_property_id: str
    buyer_alternative_set_fingerprint: str
    competitive_pressure_level: str
    competitive_pressure_fingerprint: str
    dimensions: tuple[StrategyDimension,...]
    review_triggers: tuple[ReviewTrigger,...]
    lineage_fingerprints: tuple[str,...]
    limitations: tuple[str,...]
    output_tier: str
    public_eligible: bool
    external_action_capability: str
    strategy_fingerprint: str


def load_seller_strategy_registry(path: str|Path) -> dict:
    raw=yaml.safe_load(Path(path).read_text())
    if raw.get("seller_strategy_registry_id")!="STH-M11-002-PROPERTY-SELLER-STRATEGY-v1.0":
        raise ValueError("unexpected M11-002 seller strategy registry id")
    if str(raw.get("version"))!="1.0.0" or raw.get("status")!="FROZEN":
        raise ValueError("M11-002 registry must be FROZEN v1.0")
    if raw.get("ticket")!="M11-002" or raw.get("parent_ticket")!="M11-001":
        raise ValueError("M11-002 registry lineage mismatch")
    return raw


def _eligible(row: GovernedStrategyFinding, required: Mapping[str,object]) -> bool:
    return (
        row.baseline_certified is required["baseline_certified"]
        and row.qa_status==required["qa_status"]
        and row.output_tier==required["output_tier"]
        and row.freshness_state==required["freshness_state"]
    )


def _build_dimension(
    *,
    dimension: str,
    rows: tuple[GovernedStrategyFinding,...],
    registry: Mapping[str,object],
) -> StrategyDimension:
    spec=registry["strategy_dimensions"][dimension]
    allowed=set(str(x) for x in spec["allowed_states"])
    required=registry["required_input_state"]
    current=[]
    suppressed=[]

    for row in rows:
        if row.state not in allowed:
            raise ValueError(f"{dimension}: unsupported governed state")
        _validate_fingerprint(row.evidence_fingerprint,"evidence_fingerprint")
        if row.baseline_certified is not True:
            raise ValueError("uncertified community baseline input prohibited")
        if _eligible(row,required):
            current.append(row)
        else:
            suppressed.append(row)

    if len(current)>1:
        raise ValueError(f"{dimension}: multiple current governed findings")
    if current:
        source=current[0]
        status="CURRENT"
        state=source.state
        summary=source.summary.strip()
        if not summary:
            raise ValueError(f"{dimension}: current finding summary required")
        evidence=(source.evidence_fingerprint,)
    else:
        state=None
        evidence=()
        if suppressed:
            status="SUPPRESSED"
            summary="Governed evidence exists but is not currently eligible because freshness, tier, or QA requirements are not satisfied."
        else:
            status="MISSING"
            summary="No eligible governed finding is available for this strategy dimension."

    payload={
        "dimension":dimension,
        "status":status,
        "state":state,
        "summary":summary,
        "evidence_fingerprints":evidence,
        "suppressed_finding_ids":tuple(sorted(x.finding_id for x in suppressed)),
    }
    return StrategyDimension(
        dimension=dimension,
        status=status,
        state=state,
        summary=summary,
        evidence_fingerprints=evidence,
        suppressed_finding_ids=tuple(sorted(x.finding_id for x in suppressed)),
        dimension_fingerprint=_hash(payload),
    )


def _reasons_for_day(
    *,
    day: int,
    opportunity: SellerOpportunityResult,
    dimensions: Mapping[str,StrategyDimension],
    registry: Mapping[str,object],
) -> tuple[str,...]:
    rules=registry["review_reason_rules"][f"DAY_{day}"]
    reasons=[]
    for rule in rules:
        if rule.get("always") is True:
            reasons.append(str(rule["reason"]))
            continue
        expected_pressure=rule.get("competitive_pressure")
        if expected_pressure is not None and opportunity.competitive_pressure.level==expected_pressure:
            reasons.append(str(rule["reason"]))
            continue
        for dimension in registry["strategy_dimensions"]:
            if dimension in rule:
                d=dimensions[dimension]
                if d.status=="CURRENT" and d.state==rule[dimension]:
                    reasons.append(str(rule["reason"]))
    return tuple(sorted(set(reasons)))


def _validate_prohibited_fields(strategy: PropertySellerStrategy, registry: Mapping[str,object]) -> None:
    keys=set(asdict(strategy))
    prohibited=set(str(x) for x in registry["prohibited_output_fields"])
    overlap=keys & prohibited
    if overlap:
        raise ValueError(f"prohibited strategy output fields present: {sorted(overlap)}")


def build_property_seller_strategy(
    *,
    opportunity: SellerOpportunityResult,
    m11_001_certified: bool,
    m11_001_evidence_fingerprint: str,
    findings: Iterable[GovernedStrategyFinding],
    registry: Mapping[str,object],
) -> PropertySellerStrategy:
    if m11_001_certified is not True:
        raise ValueError("certified M11-001 opportunity result required")
    _validate_fingerprint(m11_001_evidence_fingerprint,"m11_001_evidence_fingerprint")
    if opportunity.output_tier!="SELLER" or opportunity.public_eligible is not False:
        raise ValueError("M11-001 opportunity eligibility boundary violated")
    if opportunity.external_action_capability!="NONE":
        raise ValueError("M11-001 opportunity external action boundary violated")

    subject=opportunity.subject_property_id
    rows=tuple(findings)
    grouped={k:[] for k in registry["strategy_dimensions"]}
    seen=set()
    for row in rows:
        if not row.finding_id.strip():
            raise ValueError("finding_id required")
        if row.finding_id in seen:
            raise ValueError("duplicate finding_id")
        seen.add(row.finding_id)
        if row.subject_property_id!=subject:
            raise ValueError("strategy finding subject_property_id mismatch")
        if row.dimension not in grouped:
            raise ValueError("unsupported strategy dimension")
        grouped[row.dimension].append(row)

    dimensions=tuple(
        _build_dimension(dimension=name,rows=tuple(grouped[name]),registry=registry)
        for name in registry["strategy_dimensions"]
    )
    dim_map={x.dimension:x for x in dimensions}

    checkpoints={int(x["day"]):str(x["name"]) for x in registry["review_checkpoints"]}
    triggers=[]
    for day in (7,10,14):
        reasons=_reasons_for_day(day=day,opportunity=opportunity,dimensions=dim_map,registry=registry)
        triggered=bool(reasons)
        instruction=(
            "Review the governed evidence and seller strategy context. "
            "This checkpoint does not prescribe a price change, predict an outcome, or authorize an external action."
        )
        payload={
            "day":day,
            "name":checkpoints[day],
            "triggered":triggered,
            "reasons":reasons,
            "instruction":instruction,
        }
        triggers.append(ReviewTrigger(
            day=day,
            name=checkpoints[day],
            triggered=triggered,
            reasons=reasons,
            instruction=instruction,
            trigger_fingerprint=_hash(payload),
        ))

    lineage={
        m11_001_evidence_fingerprint,
        opportunity.result_fingerprint,
        opportunity.alternative_set.alternative_set_fingerprint,
        opportunity.competitive_pressure.signal_fingerprint,
    }
    limitations=[]
    for d in dimensions:
        lineage.update(d.evidence_fingerprints)
        if d.status!="CURRENT":
            limitations.append(f"{d.dimension}:{d.status}")
    lineage_tuple=tuple(sorted(lineage))
    limitations_tuple=tuple(sorted(limitations))

    payload={
        "subject_property_id":subject,
        "buyer_alternative_set_fingerprint":opportunity.alternative_set.alternative_set_fingerprint,
        "competitive_pressure_level":opportunity.competitive_pressure.level,
        "competitive_pressure_fingerprint":opportunity.competitive_pressure.signal_fingerprint,
        "dimensions":[x.dimension_fingerprint for x in dimensions],
        "review_triggers":[x.trigger_fingerprint for x in triggers],
        "lineage_fingerprints":lineage_tuple,
        "limitations":limitations_tuple,
        "output_tier":"SELLER",
        "public_eligible":False,
        "external_action_capability":"NONE",
    }
    strategy=PropertySellerStrategy(
        subject_property_id=subject,
        buyer_alternative_set_fingerprint=opportunity.alternative_set.alternative_set_fingerprint,
        competitive_pressure_level=opportunity.competitive_pressure.level,
        competitive_pressure_fingerprint=opportunity.competitive_pressure.signal_fingerprint,
        dimensions=dimensions,
        review_triggers=tuple(triggers),
        lineage_fingerprints=lineage_tuple,
        limitations=limitations_tuple,
        output_tier="SELLER",
        public_eligible=False,
        external_action_capability="NONE",
        strategy_fingerprint=_hash(payload),
    )
    _validate_prohibited_fields(strategy,registry)
    return strategy
