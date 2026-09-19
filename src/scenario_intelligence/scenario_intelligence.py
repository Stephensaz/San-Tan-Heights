from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
from typing import Iterable, Mapping, Sequence

import yaml


def _canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _hash(value: object) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _validate_fp(value: str, label: str) -> None:
    if len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
        raise ValueError(f"{label} must be lowercase sha256")


def _clean_text(value: str, label: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError(f"{label} is required")
    return value


def load_scenario_registry(path: str | Path) -> dict:
    data = yaml.safe_load(Path(path).read_text())
    if data.get("status") != "FROZEN" or data.get("ticket") != "M13-006":
        raise ValueError("M13-006 scenario registry must be FROZEN")
    if data.get("scenario_registry_id") != "STH-M13-006-SCENARIO-REGISTRY-v1.0":
        raise ValueError("unexpected M13-006 scenario registry id")
    policy = data.get("policy", {})
    for key in (
        "require_certified_baseline",
        "require_temporal_ledger_lineage",
        "require_evidence_lineage",
        "require_explicit_assumptions",
        "preserve_user_scenario_order",
        "require_unknowns_section",
        "require_limitations_section",
        "prediction_prohibited",
        "recommendation_prohibited",
        "ranking_prohibited",
        "execution_prohibited",
    ):
        if policy.get(key) is not True:
            raise ValueError(f"M13-006 policy boundary not frozen: {key}")
    return data


@dataclass(frozen=True)
class ScenarioAssumption:
    assumption_id: str
    key: str
    value: object
    kind: str
    source_fingerprints: tuple[str, ...]
    limitation: str | None
    assumption_fingerprint: str


@dataclass(frozen=True)
class ScenarioDefinition:
    scenario_id: str
    label: str
    scenario_type: str
    assumptions: tuple[ScenarioAssumption, ...]
    user_order: int
    definition_fingerprint: str


@dataclass(frozen=True)
class CertifiedScenarioBaseline:
    baseline_id: str
    community_id: str
    property_id: str
    as_of: str
    dimensions: tuple[tuple[str, object], ...]
    temporal_ledger_fingerprint: str
    source_evidence_fingerprints: tuple[str, ...]
    applicable_pattern_fingerprints: tuple[str, ...]
    unknowns: tuple[str, ...]
    limitations: tuple[str, ...]
    baseline_fingerprint: str


@dataclass(frozen=True)
class ScenarioEvidence:
    evidence_id: str
    evidence_type: str
    period_id: str
    dimensions: tuple[tuple[str, object], ...]
    source_fingerprints: tuple[str, ...]
    limitations: tuple[str, ...]
    evidence_fingerprint: str


@dataclass(frozen=True)
class ScenarioEvidenceSet:
    scenario_id: str
    evidence_ids: tuple[str, ...]
    source_fingerprints: tuple[str, ...]
    retrieval_rule: str
    evidence_set_fingerprint: str


@dataclass(frozen=True)
class ScenarioResult:
    scenario_id: str
    scenario_type: str
    baseline_fingerprint: str
    assumption_fingerprints: tuple[str, ...]
    evidence_set_fingerprint: str
    modeled_dimensions: tuple[tuple[str, object], ...]
    changed_dimensions: tuple[str, ...]
    known_facts: tuple[tuple[str, object], ...]
    unknowns: tuple[str, ...]
    limitations: tuple[str, ...]
    result_fingerprint: str


@dataclass(frozen=True)
class ScenarioDifference:
    dimension: str
    left_value: object
    right_value: object
    relation: str


@dataclass(frozen=True)
class ScenarioComparison:
    comparison_id: str
    scenario_ids: tuple[str, ...]
    pairwise_differences: tuple[tuple[str, str, tuple[ScenarioDifference, ...]], ...]
    limitations: tuple[str, ...]
    comparison_fingerprint: str


@dataclass(frozen=True)
class ScenarioExplanation:
    scenario_id: str
    facts: tuple[tuple[str, object], ...]
    assumptions: tuple[tuple[str, object], ...]
    evidence_fingerprints: tuple[str, ...]
    what_changed: tuple[str, ...]
    unknowns: tuple[str, ...]
    limitations: tuple[str, ...]
    explanation_fingerprint: str


@dataclass(frozen=True)
class ScenarioReviewPackage:
    package_id: str
    community_id: str
    property_id: str
    baseline_fingerprint: str
    temporal_ledger_fingerprint: str
    scenario_ids: tuple[str, ...]
    scenario_result_fingerprints: tuple[str, ...]
    comparison_fingerprint: str
    explanation_fingerprints: tuple[str, ...]
    certified_inputs: tuple[str, ...]
    facts: tuple[tuple[str, object], ...]
    assumptions: tuple[tuple[str, object], ...]
    evidence: tuple[str, ...]
    unknowns: tuple[str, ...]
    limitations: tuple[str, ...]
    human_decisions: tuple[str, ...]
    package_fingerprint: str


@dataclass(frozen=True)
class ScenarioCertification:
    ticket: str
    production_candidate_sha: str
    checks: tuple[tuple[str, bool], ...]
    waivers: int
    open_critical_defects: int
    decision: str
    certification_fingerprint: str


def make_assumption(
    *,
    assumption_id: str,
    key: str,
    value: object,
    kind: str,
    registry: Mapping[str, object],
    source_fingerprints: Sequence[str] = (),
    limitation: str | None = None,
) -> ScenarioAssumption:
    assumption_id = _clean_text(assumption_id, "assumption_id")
    key = _clean_text(key, "assumption key")
    if kind not in set(registry["assumption_kinds"]):
        raise ValueError("unsupported assumption kind")
    sources = tuple(sorted(set(source_fingerprints)))
    if kind == "OBSERVED" and not sources:
        raise ValueError("observed assumption requires source lineage")
    for fp in sources:
        _validate_fp(fp, "assumption source fingerprint")
    payload = {
        "assumption_id": assumption_id,
        "key": key,
        "value": value,
        "kind": kind,
        "source_fingerprints": sources,
        "limitation": limitation.strip() if limitation else None,
    }
    return ScenarioAssumption(**payload, assumption_fingerprint=_hash(payload))


def define_scenario(
    *,
    scenario_id: str,
    label: str,
    scenario_type: str,
    assumptions: Sequence[ScenarioAssumption],
    user_order: int,
    registry: Mapping[str, object],
) -> ScenarioDefinition:
    scenario_id = _clean_text(scenario_id, "scenario_id")
    label = _clean_text(label, "scenario label")
    if scenario_type not in set(registry["scenario_types"]):
        raise ValueError("unsupported scenario type")
    if user_order < 0:
        raise ValueError("user_order cannot be negative")
    rows = tuple(assumptions)
    if registry["policy"]["require_explicit_assumptions"] and scenario_type != "BASELINE" and not rows:
        raise ValueError("non-baseline scenario requires explicit assumptions")
    keys = [x.key for x in rows]
    if len(keys) != len(set(keys)):
        raise ValueError("duplicate assumption keys prohibited within scenario")
    payload = {
        "scenario_id": scenario_id,
        "label": label,
        "scenario_type": scenario_type,
        "assumptions": tuple(asdict(x) for x in rows),
        "user_order": user_order,
    }
    return ScenarioDefinition(
        scenario_id=scenario_id,
        label=label,
        scenario_type=scenario_type,
        assumptions=rows,
        user_order=user_order,
        definition_fingerprint=_hash(payload),
    )


def assemble_certified_baseline(
    *,
    baseline_id: str,
    community_id: str,
    property_id: str,
    as_of: str,
    dimensions: Mapping[str, object],
    temporal_ledger_fingerprint: str,
    source_evidence_fingerprints: Sequence[str],
    applicable_pattern_fingerprints: Sequence[str] = (),
    unknowns: Sequence[str] = (),
    limitations: Sequence[str] = (),
    registry: Mapping[str, object],
) -> CertifiedScenarioBaseline:
    for label, value in (
        ("baseline_id", baseline_id),
        ("community_id", community_id),
        ("property_id", property_id),
        ("as_of", as_of),
    ):
        _clean_text(value, label)
    _validate_fp(temporal_ledger_fingerprint, "temporal ledger fingerprint")
    evidence = tuple(sorted(set(source_evidence_fingerprints)))
    if registry["policy"]["require_evidence_lineage"] and not evidence:
        raise ValueError("certified baseline requires source evidence lineage")
    for fp in (*evidence, *applicable_pattern_fingerprints):
        _validate_fp(fp, "baseline lineage fingerprint")
    allowed = set(registry["dimensions"])
    unexpected = set(dimensions) - allowed
    if unexpected:
        raise ValueError(f"unsupported baseline dimensions: {sorted(unexpected)}")
    ordered_dimensions = tuple(sorted((str(k), v) for k, v in dimensions.items()))
    payload = {
        "baseline_id": baseline_id,
        "community_id": community_id,
        "property_id": property_id,
        "as_of": as_of,
        "dimensions": ordered_dimensions,
        "temporal_ledger_fingerprint": temporal_ledger_fingerprint,
        "source_evidence_fingerprints": evidence,
        "applicable_pattern_fingerprints": tuple(sorted(set(applicable_pattern_fingerprints))),
        "unknowns": tuple(sorted(set(x.strip() for x in unknowns if x.strip()))),
        "limitations": tuple(sorted(set(x.strip() for x in limitations if x.strip()))),
    }
    return CertifiedScenarioBaseline(**payload, baseline_fingerprint=_hash(payload))


def make_scenario_evidence(
    *,
    evidence_id: str,
    evidence_type: str,
    period_id: str,
    dimensions: Mapping[str, object],
    source_fingerprints: Sequence[str],
    limitations: Sequence[str] = (),
    registry: Mapping[str, object],
) -> ScenarioEvidence:
    for label, value in (("evidence_id", evidence_id), ("evidence_type", evidence_type), ("period_id", period_id)):
        _clean_text(value, label)
    source = tuple(sorted(set(source_fingerprints)))
    if not source:
        raise ValueError("scenario evidence requires source lineage")
    for fp in source:
        _validate_fp(fp, "evidence source fingerprint")
    allowed = set(registry["dimensions"])
    unexpected = set(dimensions) - allowed
    if unexpected:
        raise ValueError(f"unsupported evidence dimensions: {sorted(unexpected)}")
    payload = {
        "evidence_id": evidence_id,
        "evidence_type": evidence_type,
        "period_id": period_id,
        "dimensions": tuple(sorted((str(k), v) for k, v in dimensions.items())),
        "source_fingerprints": source,
        "limitations": tuple(sorted(set(x.strip() for x in limitations if x.strip()))),
    }
    return ScenarioEvidence(**payload, evidence_fingerprint=_hash(payload))


def retrieve_scenario_evidence(
    *,
    scenario: ScenarioDefinition,
    evidence: Sequence[ScenarioEvidence],
    required_dimensions: Sequence[str],
    retrieval_rule: str,
) -> ScenarioEvidenceSet:
    retrieval_rule = _clean_text(retrieval_rule, "retrieval_rule")
    required = set(required_dimensions)
    rows = []
    for item in evidence:
        item_dims = {k for k, _ in item.dimensions}
        if required.issubset(item_dims):
            rows.append(item)
    rows = sorted(rows, key=lambda x: (x.period_id, x.evidence_id))
    sources = tuple(sorted({fp for row in rows for fp in row.source_fingerprints}))
    payload = {
        "scenario_id": scenario.scenario_id,
        "evidence_ids": tuple(x.evidence_id for x in rows),
        "source_fingerprints": sources,
        "retrieval_rule": retrieval_rule,
    }
    return ScenarioEvidenceSet(**payload, evidence_set_fingerprint=_hash(payload))


def _apply_assumptions(
    baseline: CertifiedScenarioBaseline,
    scenario: ScenarioDefinition,
    allowed_assumption_keys: set[str],
) -> tuple[tuple[str, object], ...]:
    values = dict(baseline.dimensions)
    for assumption in scenario.assumptions:
        if assumption.key not in allowed_assumption_keys:
            continue
        values[assumption.key] = assumption.value
    return tuple(sorted(values.items()))


def _assert_no_prohibited_language(values: Iterable[object], registry: Mapping[str, object]) -> None:
    tokens = tuple(str(x).lower() for x in registry.get("prohibited_output_tokens", ()))
    for value in values:
        text = str(value).lower()
        for token in tokens:
            if token in text:
                raise ValueError(f"prohibited scenario language detected: {token}")


def evaluate_scenario(
    *,
    baseline: CertifiedScenarioBaseline,
    scenario: ScenarioDefinition,
    evidence_set: ScenarioEvidenceSet,
    registry: Mapping[str, object],
    additional_unknowns: Sequence[str] = (),
    additional_limitations: Sequence[str] = (),
) -> ScenarioResult:
    if not baseline.source_evidence_fingerprints:
        raise ValueError("uncertified baseline cannot be evaluated")
    if evidence_set.scenario_id != scenario.scenario_id:
        raise ValueError("scenario/evidence mismatch")
    domain_keys = {
        "BASELINE": set(),
        "PRICING_POSITION": {"pricing_position"},
        "LISTING_TIMING": {"listing_timing"},
        "BUYER_DEPTH": {"buyer_depth", "comparable_depth"},
        "SUBSTITUTION": {"substitution_requirement", "scarcity_context"},
        "COMPETITIVE_SET": {"resale_competition", "comparable_depth", "substitution_requirement"},
        "NEW_CONSTRUCTION": {"new_construction_competition", "substitution_requirement"},
    }
    allowed = domain_keys[scenario.scenario_type]
    forbidden = {x.key for x in scenario.assumptions} - set(registry["dimensions"])
    if forbidden:
        raise ValueError(f"assumptions outside governed dimensions: {sorted(forbidden)}")
    if scenario.scenario_type != "BASELINE":
        off_domain = {x.key for x in scenario.assumptions} - allowed
        if off_domain:
            raise ValueError(f"assumptions outside scenario domain: {sorted(off_domain)}")
    modeled = _apply_assumptions(baseline, scenario, allowed)
    base = dict(baseline.dimensions)
    changed = tuple(sorted(k for k, v in modeled if base.get(k) != v))
    facts = tuple(sorted(baseline.dimensions))
    unknowns = tuple(sorted(set((*baseline.unknowns, *additional_unknowns))))
    limitations = tuple(sorted(set((*baseline.limitations, *additional_limitations, *(
        x.limitation for x in scenario.assumptions if x.limitation
    )))))
    _assert_no_prohibited_language(
        [scenario.label, *(x.value for x in scenario.assumptions), *unknowns, *limitations],
        registry,
    )
    payload = {
        "scenario_id": scenario.scenario_id,
        "scenario_type": scenario.scenario_type,
        "baseline_fingerprint": baseline.baseline_fingerprint,
        "assumption_fingerprints": tuple(x.assumption_fingerprint for x in scenario.assumptions),
        "evidence_set_fingerprint": evidence_set.evidence_set_fingerprint,
        "modeled_dimensions": modeled,
        "changed_dimensions": changed,
        "known_facts": facts,
        "unknowns": unknowns,
        "limitations": limitations,
    }
    return ScenarioResult(**payload, result_fingerprint=_hash(payload))


def _relation(left: object, right: object) -> str:
    if left == right:
        return "SAME"
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        return "LEFT_LOWER" if left < right else "LEFT_HIGHER"
    return "DIFFERENT"


def compare_scenarios(
    *,
    comparison_id: str,
    scenarios: Sequence[ScenarioDefinition],
    results: Sequence[ScenarioResult],
    limitations: Sequence[str] = (),
) -> ScenarioComparison:
    comparison_id = _clean_text(comparison_id, "comparison_id")
    ordered = tuple(sorted(scenarios, key=lambda x: x.user_order))
    if len({x.user_order for x in ordered}) != len(ordered):
        raise ValueError("scenario user_order values must be unique")
    by_id = {x.scenario_id: x for x in results}
    if set(by_id) != {x.scenario_id for x in ordered}:
        raise ValueError("comparison requires exactly one result for each scenario")
    pairwise = []
    for i, left_def in enumerate(ordered):
        left = dict(by_id[left_def.scenario_id].modeled_dimensions)
        for right_def in ordered[i + 1:]:
            right = dict(by_id[right_def.scenario_id].modeled_dimensions)
            dimensions = sorted(set(left) | set(right))
            diffs = tuple(
                ScenarioDifference(
                    dimension=dimension,
                    left_value=left.get(dimension),
                    right_value=right.get(dimension),
                    relation=_relation(left.get(dimension), right.get(dimension)),
                )
                for dimension in dimensions
            )
            pairwise.append((left_def.scenario_id, right_def.scenario_id, diffs))
    payload = {
        "comparison_id": comparison_id,
        "scenario_ids": tuple(x.scenario_id for x in ordered),
        "pairwise_differences": tuple(
            (left, right, tuple(asdict(x) for x in diffs))
            for left, right, diffs in pairwise
        ),
        "limitations": tuple(sorted(set(x.strip() for x in limitations if x.strip()))),
    }
    return ScenarioComparison(
        comparison_id=comparison_id,
        scenario_ids=payload["scenario_ids"],
        pairwise_differences=tuple(pairwise),
        limitations=payload["limitations"],
        comparison_fingerprint=_hash(payload),
    )


def explain_scenario(
    *,
    scenario: ScenarioDefinition,
    result: ScenarioResult,
    evidence_set: ScenarioEvidenceSet,
) -> ScenarioExplanation:
    if scenario.scenario_id != result.scenario_id or scenario.scenario_id != evidence_set.scenario_id:
        raise ValueError("explainability inputs must refer to the same scenario")
    payload = {
        "scenario_id": scenario.scenario_id,
        "facts": result.known_facts,
        "assumptions": tuple((x.key, x.value) for x in scenario.assumptions),
        "evidence_fingerprints": evidence_set.source_fingerprints,
        "what_changed": result.changed_dimensions,
        "unknowns": result.unknowns,
        "limitations": result.limitations,
    }
    return ScenarioExplanation(**payload, explanation_fingerprint=_hash(payload))


def assemble_review_package(
    *,
    package_id: str,
    baseline: CertifiedScenarioBaseline,
    scenarios: Sequence[ScenarioDefinition],
    results: Sequence[ScenarioResult],
    comparison: ScenarioComparison,
    explanations: Sequence[ScenarioExplanation],
    human_decisions: Sequence[str] = (),
) -> ScenarioReviewPackage:
    package_id = _clean_text(package_id, "package_id")
    ordered = tuple(sorted(scenarios, key=lambda x: x.user_order))
    scenario_ids = tuple(x.scenario_id for x in ordered)
    by_result = {x.scenario_id: x for x in results}
    by_explanation = {x.scenario_id: x for x in explanations}
    if tuple(comparison.scenario_ids) != scenario_ids:
        raise ValueError("comparison order must preserve user scenario order")
    if set(by_result) != set(scenario_ids) or set(by_explanation) != set(scenario_ids):
        raise ValueError("review package requires complete scenario results and explanations")
    assumptions = tuple(
        (f"{scenario.scenario_id}:{assumption.key}", assumption.value)
        for scenario in ordered
        for assumption in scenario.assumptions
    )
    evidence = tuple(sorted({
        fp for explanation in explanations for fp in explanation.evidence_fingerprints
    }))
    unknowns = tuple(sorted({
        value for result in results for value in result.unknowns
    }))
    limitations = tuple(sorted({
        value for result in results for value in result.limitations
    } | set(comparison.limitations)))
    facts = baseline.dimensions
    payload = {
        "package_id": package_id,
        "community_id": baseline.community_id,
        "property_id": baseline.property_id,
        "baseline_fingerprint": baseline.baseline_fingerprint,
        "temporal_ledger_fingerprint": baseline.temporal_ledger_fingerprint,
        "scenario_ids": scenario_ids,
        "scenario_result_fingerprints": tuple(by_result[x].result_fingerprint for x in scenario_ids),
        "comparison_fingerprint": comparison.comparison_fingerprint,
        "explanation_fingerprints": tuple(by_explanation[x].explanation_fingerprint for x in scenario_ids),
        "certified_inputs": tuple(sorted({
            baseline.baseline_fingerprint,
            baseline.temporal_ledger_fingerprint,
            *baseline.source_evidence_fingerprints,
            *baseline.applicable_pattern_fingerprints,
        })),
        "facts": facts,
        "assumptions": assumptions,
        "evidence": evidence,
        "unknowns": unknowns,
        "limitations": limitations,
        "human_decisions": tuple(x.strip() for x in human_decisions if x.strip()),
    }
    return ScenarioReviewPackage(**payload, package_fingerprint=_hash(payload))


def validate_review_package_replay(
    package: ScenarioReviewPackage,
    *,
    baseline: CertifiedScenarioBaseline,
    scenarios: Sequence[ScenarioDefinition],
    results: Sequence[ScenarioResult],
    comparison: ScenarioComparison,
    explanations: Sequence[ScenarioExplanation],
) -> bool:
    replay = assemble_review_package(
        package_id=package.package_id,
        baseline=baseline,
        scenarios=scenarios,
        results=results,
        comparison=comparison,
        explanations=explanations,
        human_decisions=package.human_decisions,
    )
    return replay == package


def certify_m13_006(
    *,
    production_candidate_sha: str,
    package: ScenarioReviewPackage,
    replay_valid: bool,
    contract_locked: bool,
    registry_frozen: bool,
    predecessor_accepted: bool,
    coverage_complete: bool,
    adversarial_tests_passed: bool,
    temporal_tests_passed: bool,
    inherited_m12_passed: bool,
    prohibited_output_checks_passed: bool,
    waivers: int = 0,
    open_critical_defects: int = 0,
) -> ScenarioCertification:
    production_candidate_sha = _clean_text(production_candidate_sha, "production_candidate_sha")
    if len(production_candidate_sha) != 40 or any(c not in "0123456789abcdef" for c in production_candidate_sha):
        raise ValueError("production candidate must be a full lowercase git sha")
    _validate_fp(package.package_fingerprint, "review package fingerprint")
    checks = (
        ("CONTRACT_LOCKED", contract_locked),
        ("REGISTRY_FROZEN", registry_frozen),
        ("PREDECESSOR_ACCEPTED", predecessor_accepted),
        ("REVIEW_PACKAGE_REPLAY", replay_valid),
        ("COVERAGE_COMPLETE", coverage_complete),
        ("ADVERSARIAL_TESTS", adversarial_tests_passed),
        ("TEMPORAL_TESTS", temporal_tests_passed),
        ("INHERITED_M12", inherited_m12_passed),
        ("PROHIBITED_OUTPUT_BOUNDARIES", prohibited_output_checks_passed),
        ("ZERO_WAIVERS", waivers == 0),
        ("ZERO_OPEN_CRITICAL_DEFECTS", open_critical_defects == 0),
    )
    decision = "PASS_GO" if all(value for _, value in checks) else "FAIL_NO_GO"
    payload = {
        "ticket": "M13-006",
        "production_candidate_sha": production_candidate_sha,
        "checks": checks,
        "waivers": waivers,
        "open_critical_defects": open_critical_defects,
        "decision": decision,
    }
    return ScenarioCertification(**payload, certification_fingerprint=_hash(payload))
