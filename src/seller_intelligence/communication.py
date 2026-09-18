from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from pathlib import Path
from typing import Iterable, Mapping
import yaml

from src.seller_intelligence.opportunity import SellerOpportunityResult
from src.seller_intelligence.strategy import PropertySellerStrategy
from src.seller_intelligence.scenario import ScenarioSensitivityResult
from src.seller_intelligence.timeline import SellerDecisionTimeline


def _hash(payload: object) -> str:
    raw=json.dumps(payload,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode("utf-8")
    return sha256(raw).hexdigest()


def _validate_fp(value: str, label: str) -> None:
    if len(value)!=64 or any(c not in "0123456789abcdef" for c in value):
        raise ValueError(f"{label} must be lowercase sha256")


@dataclass(frozen=True)
class CommunicationStatement:
    statement_id: str
    statement_type: str
    text: str
    lineage_fingerprints: tuple[str,...]
    statement_fingerprint: str


@dataclass(frozen=True)
class SellerCommunicationProjection:
    subject_property_id: str
    audience: str
    statements: tuple[CommunicationStatement,...]
    limitations: tuple[str,...]
    qualifiers: tuple[str,...]
    source_fingerprints: tuple[str,...]
    output_tier: str
    public_eligible: bool
    external_action_capability: str
    projection_fingerprint: str


def load_communication_registry(path: str|Path) -> dict:
    raw=yaml.safe_load(Path(path).read_text())
    if raw.get("seller_communication_registry_id")!="STH-M11-005-COMMUNICATION-TRANSLATION-v1.0":
        raise ValueError("unexpected M11-005 communication registry id")
    if str(raw.get("version"))!="1.0.0" or raw.get("status")!="FROZEN":
        raise ValueError("M11-005 registry must be FROZEN v1.0")
    if raw.get("ticket")!="M11-005":
        raise ValueError("M11-005 registry ticket mismatch")
    return raw


def _statement(
    *,
    statement_id: str,
    statement_type: str,
    text: str,
    lineage: Iterable[str],
    registry: Mapping[str,object],
) -> CommunicationStatement:
    if statement_type not in set(registry["statement_types"]):
        raise ValueError("unsupported communication statement type")
    text=text.strip()
    if not text:
        raise ValueError("communication statement text required")
    fps=tuple(sorted(set(lineage)))
    for fp in fps:
        _validate_fp(fp,"statement lineage fingerprint")
    payload={
        "statement_id":statement_id,
        "statement_type":statement_type,
        "text":text,
        "lineage_fingerprints":fps,
    }
    return CommunicationStatement(
        statement_id=statement_id,
        statement_type=statement_type,
        text=text,
        lineage_fingerprints=fps,
        statement_fingerprint=_hash(payload),
    )


def _strategy_dimensions(strategy: PropertySellerStrategy) -> dict[str,object]:
    return {x.dimension:x for x in strategy.dimensions}


def _validate_inputs(
    *,
    opportunity: SellerOpportunityResult,
    strategy: PropertySellerStrategy,
    scenario: ScenarioSensitivityResult | None,
    timeline: SellerDecisionTimeline,
) -> None:
    subject=opportunity.subject_property_id
    if strategy.subject_property_id!=subject or timeline.subject_property_id!=subject:
        raise ValueError("communication input property mismatch")
    if scenario is not None and scenario.subject_property_id!=subject:
        raise ValueError("scenario communication input property mismatch")
    for item,label in ((opportunity,"M11-001"),(strategy,"M11-002"),(timeline,"M11-004")):
        if item.output_tier!="SELLER" or item.public_eligible is not False or item.external_action_capability!="NONE":
            raise ValueError(f"{label} communication eligibility boundary violated")
    if scenario is not None:
        if scenario.output_tier!="SELLER" or scenario.public_eligible is not False or scenario.external_action_capability!="NONE":
            raise ValueError("M11-003 communication eligibility boundary violated")
        if scenario.hypothetical_only is not True:
            raise ValueError("scenario must remain explicitly hypothetical")


def _validate_prohibited_fields(projection: SellerCommunicationProjection, registry: Mapping[str,object]) -> None:
    prohibited=set(str(x) for x in registry["prohibited_output_fields"])
    def walk(v: object) -> None:
        if hasattr(v,"__dataclass_fields__"):
            d=asdict(v)
            overlap=set(d)&prohibited
            if overlap:
                raise ValueError(f"prohibited communication output fields present: {sorted(overlap)}")
            for item in d.values():
                walk(item)
        elif isinstance(v,dict):
            for item in v.values():
                walk(item)
        elif isinstance(v,(tuple,list)):
            for item in v:
                walk(item)
    walk(projection)


def translate_seller_intelligence(
    *,
    audience: str,
    opportunity: SellerOpportunityResult,
    strategy: PropertySellerStrategy,
    timeline: SellerDecisionTimeline,
    m11_001_certified: bool,
    m11_002_certified: bool,
    m11_004_certified: bool,
    m11_001_evidence_fingerprint: str,
    m11_002_evidence_fingerprint: str,
    m11_004_evidence_fingerprint: str,
    registry: Mapping[str,object],
    scenario: ScenarioSensitivityResult | None = None,
    m11_003_certified: bool = False,
    m11_003_evidence_fingerprint: str | None = None,
) -> SellerCommunicationProjection:
    audience=str(audience).upper()
    if audience=="PUBLIC":
        raise ValueError("public seller-strategy communication prohibited")
    if audience not in registry["allowed_audiences"]:
        raise ValueError("unsupported communication audience")
    if not (m11_001_certified and m11_002_certified and m11_004_certified):
        raise ValueError("certified M11-001, M11-002, and M11-004 inputs required")
    for fp,label in (
        (m11_001_evidence_fingerprint,"m11_001_evidence_fingerprint"),
        (m11_002_evidence_fingerprint,"m11_002_evidence_fingerprint"),
        (m11_004_evidence_fingerprint,"m11_004_evidence_fingerprint"),
    ):
        _validate_fp(fp,label)
    if scenario is not None:
        if m11_003_certified is not True or m11_003_evidence_fingerprint is None:
            raise ValueError("certified M11-003 scenario context required")
        _validate_fp(m11_003_evidence_fingerprint,"m11_003_evidence_fingerprint")
    elif m11_003_certified or m11_003_evidence_fingerprint is not None:
        raise ValueError("scenario certification metadata supplied without scenario")

    _validate_inputs(opportunity=opportunity,strategy=strategy,scenario=scenario,timeline=timeline)
    statements=[]
    qualifiers=[
        str(registry["required_qualifiers"]["competitive_pressure"]),
        str(registry["required_qualifiers"]["monitoring"]),
    ]
    source_fps={
        opportunity.result_fingerprint,
        strategy.strategy_fingerprint,
        timeline.timeline_fingerprint,
        m11_001_evidence_fingerprint,
        m11_002_evidence_fingerprint,
        m11_004_evidence_fingerprint,
    }

    alt=opportunity.alternative_set
    statements.append(_statement(
        statement_id="FACT-BUYER-ALTERNATIVES",
        statement_type="FACT",
        text=(
            f"Current eligible buyer alternatives include {len(alt.close_substitute_ids)} close substitutes, "
            f"{len(alt.strict_substitute_ids)} strict substitutes, and {len(alt.builder_alternative_ids)} builder alternatives."
        ),
        lineage=(alt.alternative_set_fingerprint,*alt.lineage_fingerprints),
        registry=registry,
    ))
    statements.append(_statement(
        statement_id="FACT-COMPETITIVE-PRESSURE",
        statement_type="FACT",
        text=(
            f"Current governed competitive pressure is {opportunity.competitive_pressure.level}. "
            f"The signal is based on {opportunity.competitive_pressure.available_alternative_count} eligible resale alternatives "
            f"and {opportunity.competitive_pressure.builder_alternative_count} builder alternatives."
        ),
        lineage=(opportunity.competitive_pressure.signal_fingerprint,*opportunity.competitive_pressure.lineage_fingerprints),
        registry=registry,
    ))

    for d in strategy.dimensions:
        if d.status=="CURRENT":
            text=f"{d.dimension.replace('_',' ').title()} is currently classified as {d.state}. {d.summary}"
        else:
            text=f"{d.dimension.replace('_',' ').title()} is {d.status.lower()}. {d.summary}"
        statements.append(_statement(
            statement_id=f"FACT-{d.dimension}",
            statement_type="FACT",
            text=text,
            lineage=(d.dimension_fingerprint,*d.evidence_fingerprints),
            registry=registry,
        ))

    if scenario is not None:
        qualifiers.append(str(registry["required_qualifiers"]["hypothetical"]))
        source_fps.add(scenario.scenario_fingerprint)
        source_fps.add(str(m11_003_evidence_fingerprint))
        for c in scenario.comparisons:
            baseline="unavailable" if c.baseline_state is None else c.baseline_state
            statements.append(_statement(
                statement_id=f"HYPOTHETICAL-{c.target}",
                statement_type="HYPOTHETICAL",
                text=(
                    f"Hypothetical only: if {c.target.replace('_',' ').lower()} were {c.hypothetical_state}, "
                    f"the certified baseline for that target is {baseline}; comparison state is {c.change_type}."
                ),
                lineage=(c.assumption_fingerprint,c.comparison_fingerprint),
                registry=registry,
            ))

    current_entry=timeline.entries[-1]
    if current_entry.monitoring_event is not None:
        e=current_entry.monitoring_event
        statements.append(_statement(
            statement_id="MONITORING-CURRENT",
            statement_type="MONITORING_GUIDANCE",
            text=(
                "Human review is required because the certified monitoring timeline detected: "
                + ", ".join(e.reasons)
                + ". No automatic action is authorized."
            ),
            lineage=(e.event_fingerprint,current_entry.entry_fingerprint),
            registry=registry,
        ))

    limitations=tuple(sorted(set(strategy.limitations)))
    for limitation in limitations:
        statements.append(_statement(
            statement_id=f"LIMITATION-{limitation}",
            statement_type="LIMITATION",
            text=f"Limitation: {limitation}. This condition remains explicit and has not been inferred away.",
            lineage=(strategy.strategy_fingerprint,),
            registry=registry,
        ))

    source_fps.update(strategy.lineage_fingerprints)
    for fp in source_fps:
        _validate_fp(fp,"source fingerprint")
    statements=tuple(sorted(statements,key=lambda x:x.statement_id))
    qualifiers_tuple=tuple(sorted(set(qualifiers)))
    source_tuple=tuple(sorted(source_fps))
    payload={
        "subject_property_id":opportunity.subject_property_id,
        "audience":audience,
        "statements":[x.statement_fingerprint for x in statements],
        "limitations":limitations,
        "qualifiers":qualifiers_tuple,
        "source_fingerprints":source_tuple,
        "output_tier":audience,
        "public_eligible":False,
        "external_action_capability":"NONE",
    }
    projection=SellerCommunicationProjection(
        subject_property_id=opportunity.subject_property_id,
        audience=audience,
        statements=statements,
        limitations=limitations,
        qualifiers=qualifiers_tuple,
        source_fingerprints=source_tuple,
        output_tier=audience,
        public_eligible=False,
        external_action_capability="NONE",
        projection_fingerprint=_hash(payload),
    )
    _validate_prohibited_fields(projection,registry)
    return projection
