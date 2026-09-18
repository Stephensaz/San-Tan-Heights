from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
from typing import Iterable, Mapping
import yaml


def _hash(payload: object) -> str:
    raw=json.dumps(payload,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode("utf-8")
    return sha256(raw).hexdigest()


@dataclass(frozen=True)
class GovernedAlternativeInput:
    alternative_id: str
    subject_property_id: str
    alternative_property_id: str
    alternative_type: str
    baseline_certified: bool
    qa_status: str
    output_tier: str
    freshness_state: str
    evidence_fingerprint: str


@dataclass(frozen=True)
class BuyerAlternativeSet:
    subject_property_id: str
    close_substitute_ids: tuple[str,...]
    strict_substitute_ids: tuple[str,...]
    builder_alternative_ids: tuple[str,...]
    suppressed_input_ids: tuple[str,...]
    lineage_fingerprints: tuple[str,...]
    alternative_set_fingerprint: str


@dataclass(frozen=True)
class CompetitivePressureSignal:
    subject_property_id: str
    level: str
    available_alternative_count: int
    builder_alternative_count: int
    qualifier: str
    lineage_fingerprints: tuple[str,...]
    signal_fingerprint: str


@dataclass(frozen=True)
class SellerOpportunityResult:
    subject_property_id: str
    alternative_set: BuyerAlternativeSet
    competitive_pressure: CompetitivePressureSignal
    output_tier: str
    public_eligible: bool
    external_action_capability: str
    result_fingerprint: str


def load_seller_opportunity_registry(path: str|Path) -> dict:
    raw=yaml.safe_load(Path(path).read_text())
    if raw.get("seller_opportunity_registry_id")!="STH-M11-001-SELLER-OPPORTUNITY-v1.0":
        raise ValueError("unexpected M11-001 seller opportunity registry id")
    if str(raw.get("version"))!="1.0.0" or raw.get("status")!="FROZEN":
        raise ValueError("M11-001 registry must be FROZEN v1.0")
    if raw.get("ticket")!="M11-001":
        raise ValueError("M11-001 registry ticket mismatch")
    return raw


def _validate_fingerprint(value: str, label: str) -> None:
    if len(value)!=64 or any(c not in "0123456789abcdef" for c in value):
        raise ValueError(f"{label} must be lowercase sha256")


def _eligible(row: GovernedAlternativeInput, required: Mapping[str,object]) -> bool:
    return (
        row.baseline_certified is required["baseline_certified"]
        and row.qa_status==required["qa_status"]
        and row.output_tier==required["output_tier"]
        and row.freshness_state==required["freshness_state"]
    )


def _pressure_level(*, available: int, builder: int, registry: Mapping[str,object]) -> str:
    cfg=registry["competitive_pressure"]
    rules=cfg["rules"]
    for level in cfg["precedence"]:
        rule=rules[level]
        if available>=int(rule["min_available_alternatives"]) and builder>=int(rule["min_builder_alternatives"]):
            return str(level)
    raise ValueError("competitive pressure rules do not cover input state")


def build_seller_opportunity(
    *,
    subject_property_id: str,
    alternatives: Iterable[GovernedAlternativeInput],
    registry: Mapping[str,object],
) -> SellerOpportunityResult:
    subject_property_id=str(subject_property_id).strip()
    if not subject_property_id:
        raise ValueError("subject_property_id required")

    allowed_types=set(str(x) for x in registry["alternative_types"])
    required=registry["required_input_state"]
    rows=tuple(alternatives)
    seen=set()
    eligible=[]
    suppressed=[]

    for row in rows:
        if not row.alternative_id.strip():
            raise ValueError("alternative_id required")
        if row.alternative_id in seen:
            raise ValueError("duplicate alternative_id")
        seen.add(row.alternative_id)
        if row.subject_property_id!=subject_property_id:
            raise ValueError("alternative subject_property_id mismatch")
        if row.alternative_type not in allowed_types:
            raise ValueError("unsupported alternative_type")
        _validate_fingerprint(row.evidence_fingerprint,"evidence_fingerprint")
        if row.baseline_certified is not True:
            raise ValueError("uncertified community baseline input prohibited")
        if _eligible(row,required):
            eligible.append(row)
        else:
            suppressed.append(row)

    def ids(kind: str) -> tuple[str,...]:
        return tuple(sorted(r.alternative_property_id for r in eligible if r.alternative_type==kind))

    close_ids=ids("CLOSE_SUBSTITUTE")
    strict_ids=ids("STRICT_SUBSTITUTE")
    builder_ids=ids("BUILDER_ALTERNATIVE")
    lineage=tuple(sorted(set(r.evidence_fingerprint for r in eligible)))

    alt_payload={
        "subject_property_id":subject_property_id,
        "close_substitute_ids":close_ids,
        "strict_substitute_ids":strict_ids,
        "builder_alternative_ids":builder_ids,
        "suppressed_input_ids":tuple(sorted(r.alternative_id for r in suppressed)),
        "lineage_fingerprints":lineage,
    }
    alternative_set=BuyerAlternativeSet(
        subject_property_id=subject_property_id,
        close_substitute_ids=close_ids,
        strict_substitute_ids=strict_ids,
        builder_alternative_ids=builder_ids,
        suppressed_input_ids=tuple(sorted(r.alternative_id for r in suppressed)),
        lineage_fingerprints=lineage,
        alternative_set_fingerprint=_hash(alt_payload),
    )

    available=len(set(close_ids+strict_ids))
    builder=len(builder_ids)
    level=_pressure_level(available=available,builder=builder,registry=registry)
    qualifier=(
        "Competitive pressure is a governed relative signal based only on current eligible alternatives; "
        "it is not a valuation, list-price recommendation, sale-price prediction, or outcome guarantee."
    )
    pressure_payload={
        "subject_property_id":subject_property_id,
        "level":level,
        "available_alternative_count":available,
        "builder_alternative_count":builder,
        "qualifier":qualifier,
        "lineage_fingerprints":lineage,
    }
    pressure=CompetitivePressureSignal(
        subject_property_id=subject_property_id,
        level=level,
        available_alternative_count=available,
        builder_alternative_count=builder,
        qualifier=qualifier,
        lineage_fingerprints=lineage,
        signal_fingerprint=_hash(pressure_payload),
    )

    result_payload={
        "subject_property_id":subject_property_id,
        "alternative_set_fingerprint":alternative_set.alternative_set_fingerprint,
        "competitive_pressure_fingerprint":pressure.signal_fingerprint,
        "output_tier":"SELLER",
        "public_eligible":False,
        "external_action_capability":"NONE",
    }
    return SellerOpportunityResult(
        subject_property_id=subject_property_id,
        alternative_set=alternative_set,
        competitive_pressure=pressure,
        output_tier="SELLER",
        public_eligible=False,
        external_action_capability="NONE",
        result_fingerprint=_hash(result_payload),
    )
