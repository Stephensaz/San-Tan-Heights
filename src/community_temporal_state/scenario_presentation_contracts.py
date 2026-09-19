from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
from typing import Mapping, Sequence
import yaml

from src.community_temporal_state.scenario_explainability import (
    ScenarioExplanation,
    ComparisonExplanation,
)


def _canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _hash(value: object) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _validate_fp(value: str, label: str) -> None:
    if len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
        raise ValueError(f"{label} must be lowercase sha256")


def load_presentation_contract_registry(path: str | Path) -> dict:
    data = yaml.safe_load(Path(path).read_text())
    if data.get("status") != "FROZEN" or data.get("ticket") != "M13-006I":
        raise ValueError("M13-006I presentation registry must be FROZEN")
    if data.get("scenario_presentation_registry_id") != "STH-M13-006I-PRESENTATION-CONTRACTS-v1.0":
        raise ValueError("unexpected M13-006I registry id")
    return data


@dataclass(frozen=True)
class PresentationSection:
    section_id: str
    visibility: str
    content: object
    suppression_reason: str | None
    section_fingerprint: str


@dataclass(frozen=True)
class ScenarioPresentationContract:
    contract_id: str
    tier: str
    scenario_id: str
    source_explanation_fingerprint: str
    sections: tuple[PresentationSection, ...]
    required_disclosures: tuple[str, ...]
    screen_eligible: bool
    export_eligible: bool
    policy_version: str
    contract_fingerprint: str


@dataclass(frozen=True)
class ComparisonPresentationContract:
    contract_id: str
    tier: str
    comparison_id: str
    source_explanation_fingerprint: str
    scenario_ids: tuple[str, ...]
    sections: tuple[PresentationSection, ...]
    required_disclosures: tuple[str, ...]
    screen_eligible: bool
    export_eligible: bool
    policy_version: str
    contract_fingerprint: str


def _section(
    section_id: str,
    visibility: str,
    content: object,
    *,
    suppression_reason: str | None = None,
) -> PresentationSection:
    if visibility == "SUPPRESSED" and not suppression_reason:
        raise ValueError("suppressed section requires reason code")
    if visibility != "SUPPRESSED" and suppression_reason is not None:
        raise ValueError("suppression reason only valid for suppressed section")
    payload = {
        "section_id": section_id,
        "visibility": visibility,
        "content": content,
        "suppression_reason": suppression_reason,
    }
    return PresentationSection(**payload, section_fingerprint=_hash(payload))


def _mandatory_disclosures(registry: Mapping[str, object]) -> tuple[str, ...]:
    return tuple(registry["mandatory_disclosures"])


def _visibility(tier: str, section_id: str, registry: Mapping[str, object]) -> str:
    key = "agent_visibility" if tier == "AGENT" else "seller_visibility"
    return registry[key][section_id]


def _seller_fact_summary(facts: Sequence[tuple[str, object]]) -> tuple[tuple[str, object], ...]:
    # Seller simplification is a deterministic projection of the exact fact set.
    # Values are not interpreted or strengthened.
    allowed = {
        "reference_price",
        "reference_date",
        "current_buyer_depth",
        "current_comparable_depth",
        "current_resale_competition",
        "current_substitution_requirement",
        "scarcity_context",
        "current_new_construction_competition",
        "current_builder_inventory",
        "current_builder_incentive_value",
        "current_builder_incentive_posture",
    }
    return tuple((k, v) for k, v in facts if k in allowed)


def _seller_assumption_summary(assumptions: Sequence[tuple[str, object]]) -> tuple[tuple[str, object], ...]:
    allowed = {
        "candidate_list_price",
        "candidate_listing_date",
        "candidate_buyer_depth",
        "candidate_comparable_depth",
        "candidate_resale_competition",
        "candidate_substitution_requirement",
        "candidate_new_construction_competition",
        "candidate_builder_inventory",
        "candidate_builder_incentive_value",
        "candidate_builder_incentive_posture",
    }
    return tuple((k, v) for k, v in assumptions if k in allowed)


def build_scenario_presentation_contract(
    *,
    contract_id: str,
    tier: str,
    explanation: ScenarioExplanation,
    registry: Mapping[str, object],
) -> ScenarioPresentationContract:
    if tier not in set(registry["tiers"]):
        raise ValueError("unsupported presentation tier")
    _validate_fp(explanation.explanation_fingerprint, "scenario explanation fingerprint")

    vis = lambda section: _visibility(tier, section, registry)
    sections: list[PresentationSection] = []

    fact_content = explanation.facts if tier == "AGENT" else _seller_fact_summary(explanation.facts)
    assumption_content = explanation.assumptions if tier == "AGENT" else _seller_assumption_summary(explanation.assumptions)

    sections.append(_section("FACTS", vis("FACTS"), fact_content))
    sections.append(_section("ASSUMPTIONS", vis("ASSUMPTIONS"), assumption_content))
    sections.append(_section("MODELED_DIMENSIONS", vis("MODELED_DIMENSIONS"), explanation.modeled_dimensions))
    sections.append(_section("CHANGED_FROM_REFERENCE", vis("CHANGED_FROM_REFERENCE"), explanation.changed_from_reference))

    evidence_visibility = vis("EVIDENCE_LINEAGE")
    if evidence_visibility == "SUPPRESSED":
        reason = registry["suppression_reasons"]["EVIDENCE_LINEAGE"][tier]
        sections.append(_section("EVIDENCE_LINEAGE", evidence_visibility, (), suppression_reason=reason))
    else:
        sections.append(_section("EVIDENCE_LINEAGE", evidence_visibility, {
            "source_fingerprints": explanation.evidence_source_fingerprints,
            "evidence_fingerprints": explanation.evidence_fingerprints,
        }))

    sections.append(_section("PROMOTED_PATTERNS", vis("PROMOTED_PATTERNS"), explanation.applicable_pattern_ids))
    sections.append(_section("UNKNOWNS", vis("UNKNOWNS"), explanation.unknowns))
    sections.append(_section("LIMITATIONS", vis("LIMITATIONS"), explanation.limitations))
    sections.append(_section("COMPARISON_DIFFERENCES", "NOT_APPLICABLE", ()))
    sections.append(_section("DISCLOSURES", vis("DISCLOSURES"), _mandatory_disclosures(registry)))

    payload = {
        "contract_id": contract_id,
        "tier": tier,
        "scenario_id": explanation.scenario_id,
        "source_explanation_fingerprint": explanation.explanation_fingerprint,
        "sections": tuple(asdict(x) for x in sections),
        "required_disclosures": _mandatory_disclosures(registry),
        "screen_eligible": bool(registry["screen_eligibility"][tier]),
        "export_eligible": bool(registry["export_eligibility"][tier]),
        "policy_version": str(registry["version"]),
    }
    return ScenarioPresentationContract(
        contract_id=contract_id,
        tier=tier,
        scenario_id=explanation.scenario_id,
        source_explanation_fingerprint=explanation.explanation_fingerprint,
        sections=tuple(sections),
        required_disclosures=_mandatory_disclosures(registry),
        screen_eligible=bool(registry["screen_eligibility"][tier]),
        export_eligible=bool(registry["export_eligibility"][tier]),
        policy_version=str(registry["version"]),
        contract_fingerprint=_hash(payload),
    )


def build_comparison_presentation_contract(
    *,
    contract_id: str,
    tier: str,
    explanation: ComparisonExplanation,
    registry: Mapping[str, object],
) -> ComparisonPresentationContract:
    if tier not in set(registry["tiers"]):
        raise ValueError("unsupported presentation tier")
    _validate_fp(explanation.explanation_fingerprint, "comparison explanation fingerprint")

    vis = lambda section: _visibility(tier, section, registry)
    rows = explanation.pairwise_differences
    # Seller simplification preserves exact pairwise values/relations but drops no
    # qualifier needed to interpret them. Rendering is owned by M13-006J.
    comparison_content = rows

    sections = (
        _section("FACTS", "NOT_APPLICABLE", ()),
        _section("ASSUMPTIONS", "NOT_APPLICABLE", ()),
        _section("MODELED_DIMENSIONS", "NOT_APPLICABLE", ()),
        _section("CHANGED_FROM_REFERENCE", "NOT_APPLICABLE", ()),
        _section(
            "EVIDENCE_LINEAGE",
            vis("EVIDENCE_LINEAGE"),
            () if vis("EVIDENCE_LINEAGE") == "SUPPRESSED" else explanation.scenario_explanation_fingerprints,
            suppression_reason=(
                registry["suppression_reasons"]["EVIDENCE_LINEAGE"][tier]
                if vis("EVIDENCE_LINEAGE") == "SUPPRESSED"
                else None
            ),
        ),
        _section("PROMOTED_PATTERNS", "NOT_APPLICABLE", ()),
        _section("UNKNOWNS", vis("UNKNOWNS"), explanation.unknowns),
        _section("LIMITATIONS", vis("LIMITATIONS"), explanation.limitations),
        _section("COMPARISON_DIFFERENCES", vis("COMPARISON_DIFFERENCES"), comparison_content),
        _section("DISCLOSURES", vis("DISCLOSURES"), _mandatory_disclosures(registry)),
    )

    payload = {
        "contract_id": contract_id,
        "tier": tier,
        "comparison_id": explanation.comparison_id,
        "source_explanation_fingerprint": explanation.explanation_fingerprint,
        "scenario_ids": explanation.scenario_ids,
        "sections": tuple(asdict(x) for x in sections),
        "required_disclosures": _mandatory_disclosures(registry),
        "screen_eligible": bool(registry["screen_eligibility"][tier]),
        "export_eligible": bool(registry["export_eligibility"][tier]),
        "policy_version": str(registry["version"]),
    }
    return ComparisonPresentationContract(
        contract_id=contract_id,
        tier=tier,
        comparison_id=explanation.comparison_id,
        source_explanation_fingerprint=explanation.explanation_fingerprint,
        scenario_ids=explanation.scenario_ids,
        sections=sections,
        required_disclosures=_mandatory_disclosures(registry),
        screen_eligible=bool(registry["screen_eligibility"][tier]),
        export_eligible=bool(registry["export_eligibility"][tier]),
        policy_version=str(registry["version"]),
        contract_fingerprint=_hash(payload),
    )


def validate_scenario_presentation_replay(
    contract: ScenarioPresentationContract,
    *,
    explanation: ScenarioExplanation,
    registry: Mapping[str, object],
) -> bool:
    return build_scenario_presentation_contract(
        contract_id=contract.contract_id,
        tier=contract.tier,
        explanation=explanation,
        registry=registry,
    ) == contract


def validate_comparison_presentation_replay(
    contract: ComparisonPresentationContract,
    *,
    explanation: ComparisonExplanation,
    registry: Mapping[str, object],
) -> bool:
    return build_comparison_presentation_contract(
        contract_id=contract.contract_id,
        tier=contract.tier,
        explanation=explanation,
        registry=registry,
    ) == contract


def validate_semantic_equivalence(
    *,
    agent: ScenarioPresentationContract,
    seller: ScenarioPresentationContract,
) -> bool:
    if agent.scenario_id != seller.scenario_id:
        return False
    if agent.source_explanation_fingerprint != seller.source_explanation_fingerprint:
        return False

    a = {x.section_id: x for x in agent.sections}
    s = {x.section_id: x for x in seller.sections}

    for required in ("UNKNOWNS", "LIMITATIONS", "DISCLOSURES", "CHANGED_FROM_REFERENCE"):
        if a[required].content != s[required].content:
            return False

    # Seller facts/assumptions may be strict deterministic subsets only.
    if not set(s["FACTS"].content).issubset(set(a["FACTS"].content)):
        return False
    if not set(s["ASSUMPTIONS"].content).issubset(set(a["ASSUMPTIONS"].content)):
        return False

    # Suppression must remain explicit.
    for section in seller.sections:
        if section.visibility == "SUPPRESSED" and not section.suppression_reason:
            return False
    return True


def assert_seller_payload_isolated(contract: ScenarioPresentationContract | ComparisonPresentationContract) -> None:
    if contract.tier != "SELLER":
        raise ValueError("seller isolation check requires SELLER contract")
    for section in contract.sections:
        if section.section_id == "EVIDENCE_LINEAGE":
            if section.visibility != "SUPPRESSED" or section.content not in ((), {}):
                raise ValueError("seller payload contains Agent-only evidence lineage")
