from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from src.scenario_intelligence import (
    assemble_certified_baseline,
    assemble_review_package,
    certify_m13_006,
    compare_scenarios,
    define_scenario,
    evaluate_scenario,
    explain_scenario,
    load_scenario_registry,
    make_assumption,
    make_scenario_evidence,
    retrieve_scenario_evidence,
    validate_review_package_replay,
)


REGISTRY_PATH = Path("registries/community_temporal_state/STH-M13-006-SCENARIO-REGISTRY-v1.0.yaml")
FP1 = hashlib.sha256(b"source-1").hexdigest()
FP2 = hashlib.sha256(b"source-2").hexdigest()
LEDGER = hashlib.sha256(b"ledger").hexdigest()
PATTERN = hashlib.sha256(b"promoted-pattern").hexdigest()


@pytest.fixture
def registry():
    return load_scenario_registry(REGISTRY_PATH)


@pytest.fixture
def baseline(registry):
    return assemble_certified_baseline(
        baseline_id="BASE-1",
        community_id="STH",
        property_id="P-100",
        as_of="2026-09-18T18:00:00-07:00",
        dimensions={
            "pricing_position": 100.0,
            "listing_timing": "CURRENT",
            "buyer_depth": 4,
            "comparable_depth": 6,
            "substitution_requirement": "LOW",
            "scarcity_context": "NORMAL",
            "resale_competition": 5,
            "new_construction_competition": 3,
            "historical_support": "MODERATE",
            "coverage": 0.92,
            "uncertainty": "MODERATE",
        },
        temporal_ledger_fingerprint=LEDGER,
        source_evidence_fingerprints=(FP1, FP2),
        applicable_pattern_fingerprints=(PATTERN,),
        unknowns=("future buyer behavior is unknown",),
        limitations=("scenario outputs are descriptive, not forecasts",),
        registry=registry,
    )


def _scenario(registry, scenario_id="S1", user_order=0, value=98.0):
    assumption = make_assumption(
        assumption_id=f"A-{scenario_id}",
        key="pricing_position",
        value=value,
        kind="USER_SUPPLIED",
        registry=registry,
        limitation="illustrative user-supplied scenario input",
    )
    return define_scenario(
        scenario_id=scenario_id,
        label=f"Scenario {scenario_id}",
        scenario_type="PRICING_POSITION",
        assumptions=(assumption,),
        user_order=user_order,
        registry=registry,
    )


def _evidence(registry, evidence_id="E1", period_id="2026-W36"):
    return make_scenario_evidence(
        evidence_id=evidence_id,
        evidence_type="HISTORICAL_ANALOG",
        period_id=period_id,
        dimensions={"pricing_position": 99.0, "buyer_depth": 3},
        source_fingerprints=(FP1,),
        limitations=("historical association is not a prediction",),
        registry=registry,
    )


def _result(registry, baseline, scenario, evidence):
    evidence_set = retrieve_scenario_evidence(
        scenario=scenario,
        evidence=(evidence,),
        required_dimensions=("pricing_position",),
        retrieval_rule="same governed dimension with deterministic period ordering",
    )
    result = evaluate_scenario(
        baseline=baseline,
        scenario=scenario,
        evidence_set=evidence_set,
        registry=registry,
    )
    return evidence_set, result


def test_registry_is_frozen(registry):
    assert registry["status"] == "FROZEN"
    assert registry["ticket"] == "M13-006"
    assert registry["policy"]["prediction_prohibited"] is True
    assert registry["policy"]["recommendation_prohibited"] is True
    assert registry["policy"]["ranking_prohibited"] is True
    assert registry["policy"]["execution_prohibited"] is True


def test_observed_assumption_requires_lineage(registry):
    with pytest.raises(ValueError, match="source lineage"):
        make_assumption(
            assumption_id="A1",
            key="buyer_depth",
            value=4,
            kind="OBSERVED",
            registry=registry,
        )


def test_nonbaseline_scenario_requires_explicit_assumption(registry):
    with pytest.raises(ValueError, match="explicit assumptions"):
        define_scenario(
            scenario_id="S1",
            label="Scenario",
            scenario_type="BUYER_DEPTH",
            assumptions=(),
            user_order=0,
            registry=registry,
        )


def test_duplicate_assumption_keys_prohibited(registry):
    a1 = make_assumption(
        assumption_id="A1", key="buyer_depth", value=3,
        kind="USER_SUPPLIED", registry=registry,
    )
    a2 = make_assumption(
        assumption_id="A2", key="buyer_depth", value=5,
        kind="USER_SUPPLIED", registry=registry,
    )
    with pytest.raises(ValueError, match="duplicate assumption keys"):
        define_scenario(
            scenario_id="S1", label="Scenario", scenario_type="BUYER_DEPTH",
            assumptions=(a1, a2), user_order=0, registry=registry,
        )


def test_baseline_requires_evidence_lineage(registry):
    with pytest.raises(ValueError, match="source evidence lineage"):
        assemble_certified_baseline(
            baseline_id="B", community_id="STH", property_id="P1", as_of="now",
            dimensions={"buyer_depth": 1},
            temporal_ledger_fingerprint=LEDGER,
            source_evidence_fingerprints=(),
            registry=registry,
        )


def test_baseline_rejects_unknown_dimension(registry):
    with pytest.raises(ValueError, match="unsupported baseline dimensions"):
        assemble_certified_baseline(
            baseline_id="B", community_id="STH", property_id="P1", as_of="now",
            dimensions={"secret_score": 1},
            temporal_ledger_fingerprint=LEDGER,
            source_evidence_fingerprints=(FP1,),
            registry=registry,
        )


def test_evidence_requires_lineage(registry):
    with pytest.raises(ValueError, match="source lineage"):
        make_scenario_evidence(
            evidence_id="E", evidence_type="ANALOG", period_id="P",
            dimensions={"buyer_depth": 2}, source_fingerprints=(), registry=registry,
        )


def test_evidence_retrieval_is_deterministic(registry):
    scenario = _scenario(registry)
    e2 = _evidence(registry, "E2", "2026-W37")
    e1 = _evidence(registry, "E1", "2026-W36")
    one = retrieve_scenario_evidence(
        scenario=scenario, evidence=(e2, e1),
        required_dimensions=("pricing_position",), retrieval_rule="frozen",
    )
    two = retrieve_scenario_evidence(
        scenario=scenario, evidence=(e1, e2),
        required_dimensions=("pricing_position",), retrieval_rule="frozen",
    )
    assert one == two
    assert one.evidence_ids == ("E1", "E2")


def test_pricing_scenario_changes_only_pricing_dimension(registry, baseline):
    scenario = _scenario(registry, value=97.5)
    evidence_set, result = _result(registry, baseline, scenario, _evidence(registry))
    assert result.changed_dimensions == ("pricing_position",)
    assert dict(result.modeled_dimensions)["pricing_position"] == 97.5
    assert evidence_set.scenario_id == scenario.scenario_id


def test_scenario_cannot_modify_off_domain_dimension(registry, baseline):
    assumption = make_assumption(
        assumption_id="A1", key="buyer_depth", value=99,
        kind="USER_SUPPLIED", registry=registry,
    )
    scenario = define_scenario(
        scenario_id="S1", label="Pricing", scenario_type="PRICING_POSITION",
        assumptions=(assumption,), user_order=0, registry=registry,
    )
    evidence_set = retrieve_scenario_evidence(
        scenario=scenario, evidence=(_evidence(registry),),
        required_dimensions=("pricing_position",), retrieval_rule="frozen",
    )
    with pytest.raises(ValueError, match="outside scenario domain"):
        evaluate_scenario(
            baseline=baseline, scenario=scenario,
            evidence_set=evidence_set, registry=registry,
        )


@pytest.mark.parametrize("bad_label", [
    "Best Scenario",
    "Recommended path",
    "Winner case",
    "Optimal choice",
    "You should choose this",
    "This will sell",
    "Likely to sell",
    "Guaranteed result",
])
def test_prohibited_recommendation_prediction_language_is_rejected(
    registry, baseline, bad_label
):
    assumption = make_assumption(
        assumption_id="A1", key="pricing_position", value=99,
        kind="USER_SUPPLIED", registry=registry,
    )
    scenario = define_scenario(
        scenario_id="S1", label=bad_label, scenario_type="PRICING_POSITION",
        assumptions=(assumption,), user_order=0, registry=registry,
    )
    evidence_set = retrieve_scenario_evidence(
        scenario=scenario, evidence=(_evidence(registry),),
        required_dimensions=("pricing_position",), retrieval_rule="frozen",
    )
    with pytest.raises(ValueError, match="prohibited scenario language"):
        evaluate_scenario(
            baseline=baseline, scenario=scenario,
            evidence_set=evidence_set, registry=registry,
        )


def test_comparison_preserves_human_order_and_does_not_pick_winner(registry, baseline):
    s2 = _scenario(registry, "S2", 1, 96.0)
    s1 = _scenario(registry, "S1", 0, 100.0)
    es1, r1 = _result(registry, baseline, s1, _evidence(registry, "E1"))
    es2, r2 = _result(registry, baseline, s2, _evidence(registry, "E2"))
    comparison = compare_scenarios(
        comparison_id="C1",
        scenarios=(s2, s1),
        results=(r2, r1),
        limitations=("side-by-side description only",),
    )
    assert comparison.scenario_ids == ("S1", "S2")
    assert not hasattr(comparison, "winner")
    assert not hasattr(comparison, "score")
    assert comparison.pairwise_differences[0][0:2] == ("S1", "S2")


def test_duplicate_human_order_is_rejected(registry, baseline):
    s1 = _scenario(registry, "S1", 0, 100.0)
    s2 = _scenario(registry, "S2", 0, 96.0)
    _, r1 = _result(registry, baseline, s1, _evidence(registry, "E1"))
    _, r2 = _result(registry, baseline, s2, _evidence(registry, "E2"))
    with pytest.raises(ValueError, match="user_order"):
        compare_scenarios(
            comparison_id="C1", scenarios=(s1, s2), results=(r1, r2)
        )


def test_explainability_surfaces_facts_assumptions_unknowns_and_limitations(registry, baseline):
    scenario = _scenario(registry)
    evidence_set, result = _result(registry, baseline, scenario, _evidence(registry))
    explanation = explain_scenario(
        scenario=scenario, result=result, evidence_set=evidence_set
    )
    assert ("pricing_position", 100.0) in explanation.facts
    assert ("pricing_position", 98.0) in explanation.assumptions
    assert "future buyer behavior is unknown" in explanation.unknowns
    assert explanation.limitations
    assert explanation.evidence_fingerprints == (FP1,)


def _complete_package(registry, baseline):
    s1 = _scenario(registry, "S1", 0, 100.0)
    s2 = _scenario(registry, "S2", 1, 97.0)
    es1, r1 = _result(registry, baseline, s1, _evidence(registry, "E1"))
    es2, r2 = _result(registry, baseline, s2, _evidence(registry, "E2"))
    comparison = compare_scenarios(
        comparison_id="C1",
        scenarios=(s1, s2),
        results=(r1, r2),
        limitations=("no scenario is ranked or recommended",),
    )
    x1 = explain_scenario(scenario=s1, result=r1, evidence_set=es1)
    x2 = explain_scenario(scenario=s2, result=r2, evidence_set=es2)
    package = assemble_review_package(
        package_id="PKG1",
        baseline=baseline,
        scenarios=(s1, s2),
        results=(r1, r2),
        comparison=comparison,
        explanations=(x1, x2),
        human_decisions=("seller chooses which scenario, if any, to use",),
    )
    return (s1, s2), (r1, r2), comparison, (x1, x2), package


def test_review_package_contains_all_governed_sections(registry, baseline):
    scenarios, results, comparison, explanations, package = _complete_package(registry, baseline)
    assert package.certified_inputs
    assert package.facts
    assert package.assumptions
    assert package.evidence
    assert package.unknowns
    assert package.limitations
    assert package.human_decisions
    assert package.scenario_ids == ("S1", "S2")
    assert baseline.temporal_ledger_fingerprint == package.temporal_ledger_fingerprint


def test_review_package_replay_is_deterministic(registry, baseline):
    scenarios, results, comparison, explanations, package = _complete_package(registry, baseline)
    assert validate_review_package_replay(
        package,
        baseline=baseline,
        scenarios=scenarios,
        results=results,
        comparison=comparison,
        explanations=explanations,
    )


def test_review_package_rejects_mismatched_comparison_order(registry, baseline):
    scenarios, results, comparison, explanations, package = _complete_package(registry, baseline)
    reversed_scenarios = tuple(reversed(scenarios))
    with pytest.raises(ValueError, match="comparison order"):
        assemble_review_package(
            package_id="PKG2",
            baseline=baseline,
            scenarios=tuple(
                define_scenario(
                    scenario_id=s.scenario_id,
                    label=s.label,
                    scenario_type=s.scenario_type,
                    assumptions=s.assumptions,
                    user_order=1 - s.user_order,
                    registry=registry,
                )
                for s in reversed_scenarios
            ),
            results=results,
            comparison=comparison,
            explanations=explanations,
        )


def test_certification_pass_go_requires_every_check(registry, baseline):
    scenarios, results, comparison, explanations, package = _complete_package(registry, baseline)
    cert = certify_m13_006(
        production_candidate_sha="a" * 40,
        package=package,
        replay_valid=True,
        contract_locked=True,
        registry_frozen=True,
        predecessor_accepted=True,
        coverage_complete=True,
        adversarial_tests_passed=True,
        temporal_tests_passed=True,
        inherited_m12_passed=True,
        prohibited_output_checks_passed=True,
    )
    assert cert.decision == "PASS_GO"


@pytest.mark.parametrize("failed_key", [
    "replay_valid",
    "contract_locked",
    "registry_frozen",
    "predecessor_accepted",
    "coverage_complete",
    "adversarial_tests_passed",
    "temporal_tests_passed",
    "inherited_m12_passed",
    "prohibited_output_checks_passed",
])
def test_certification_fail_no_go_on_any_failed_gate(registry, baseline, failed_key):
    _, _, _, _, package = _complete_package(registry, baseline)
    kwargs = {
        "replay_valid": True,
        "contract_locked": True,
        "registry_frozen": True,
        "predecessor_accepted": True,
        "coverage_complete": True,
        "adversarial_tests_passed": True,
        "temporal_tests_passed": True,
        "inherited_m12_passed": True,
        "prohibited_output_checks_passed": True,
    }
    kwargs[failed_key] = False
    cert = certify_m13_006(
        production_candidate_sha="b" * 40,
        package=package,
        **kwargs,
    )
    assert cert.decision == "FAIL_NO_GO"


def test_certification_fails_on_waiver(registry, baseline):
    _, _, _, _, package = _complete_package(registry, baseline)
    cert = certify_m13_006(
        production_candidate_sha="c" * 40,
        package=package,
        replay_valid=True,
        contract_locked=True,
        registry_frozen=True,
        predecessor_accepted=True,
        coverage_complete=True,
        adversarial_tests_passed=True,
        temporal_tests_passed=True,
        inherited_m12_passed=True,
        prohibited_output_checks_passed=True,
        waivers=1,
    )
    assert cert.decision == "FAIL_NO_GO"


def test_certification_fails_on_open_critical_defect(registry, baseline):
    _, _, _, _, package = _complete_package(registry, baseline)
    cert = certify_m13_006(
        production_candidate_sha="d" * 40,
        package=package,
        replay_valid=True,
        contract_locked=True,
        registry_frozen=True,
        predecessor_accepted=True,
        coverage_complete=True,
        adversarial_tests_passed=True,
        temporal_tests_passed=True,
        inherited_m12_passed=True,
        prohibited_output_checks_passed=True,
        open_critical_defects=1,
    )
    assert cert.decision == "FAIL_NO_GO"


def test_certification_requires_exact_full_candidate_sha(registry, baseline):
    _, _, _, _, package = _complete_package(registry, baseline)
    with pytest.raises(ValueError, match="full lowercase git sha"):
        certify_m13_006(
            production_candidate_sha="abc123",
            package=package,
            replay_valid=True,
            contract_locked=True,
            registry_frozen=True,
            predecessor_accepted=True,
            coverage_complete=True,
            adversarial_tests_passed=True,
            temporal_tests_passed=True,
            inherited_m12_passed=True,
            prohibited_output_checks_passed=True,
        )
