from dataclasses import asdict, fields
import hashlib
import json

import pytest

from src.community_temporal_state.patterns import GovernedPatternCandidate, PatternEstimate
from src.community_temporal_state.scenario_baseline import (
    CertifiedScenarioBaseline,
    PatternApplicability,
    PatternApplicabilityRule,
    assemble_certified_scenario_baseline,
    assess_pattern_applicability,
    load_certified_baseline_registry,
    make_pattern_applicability_rule,
    validate_certified_scenario_baseline_replay,
)
from src.community_temporal_state.scenario_governance import (
    build_scenario_contract,
    load_scenario_governance_registry,
    make_scenario_assumption,
    make_scenario_fact,
    ready_scenario_contract,
)

B_REGISTRY = "registries/community_temporal_state/m13-006b-certified-baseline-v1.0.yaml"
A_REGISTRY = "registries/community_temporal_state/m13-006a-scenario-governance-v1.0.yaml"
SOURCE_FP = "a" * 64
BASELINE_FP = "b" * 64
LEDGER_FP = "c" * 64


def _hash(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()


def b_registry():
    return load_certified_baseline_registry(B_REGISTRY)


def ready_contract():
    ar = load_scenario_governance_registry(A_REGISTRY)
    fact = make_scenario_fact(
        key="phase",
        value="C-1",
        source_artifact_id="SNAPSHOT-1",
        source_fingerprint=SOURCE_FP,
    )
    assumption = make_scenario_assumption(
        key="candidate_list_price",
        assumption_type="MONEY",
        value=525000,
        source="HUMAN_EXPLICIT",
        limitation="Scenario input only.",
        registry=ar,
    )
    draft = build_scenario_contract(
        scenario_id="SCENARIO-1",
        contract_version=1,
        community_id="SAN-TAN-HEIGHTS",
        subject_id="PROPERTY-1",
        baseline_snapshot_id="SNAPSHOT-1",
        baseline_status="CERTIFIED",
        baseline_fingerprint=BASELINE_FP,
        facts=(fact,),
        assumptions=(assumption,),
        policy_version="M13-006A-v1.0",
        registry=ar,
    )
    return ready_scenario_contract(draft)


def promoted_pattern(pattern_id="PATTERN-1", domain="pricing", limitation="Historical association only."):
    estimate = PatternEstimate(
        population_id="POP-1",
        n=30,
        distinct_periods=5,
        effect_direction="NEGATIVE",
        effect_magnitude=0.2,
        estimate_fingerprint="d" * 64,
    )
    payload = {
        "pattern_id": pattern_id,
        "domain": domain,
        "statement": "Observed historical pricing-position association.",
        "discovery_population_id": "D",
        "validation_population_id": "V",
        "replication_population_id": "R",
        "discovery_estimate": asdict(estimate),
        "validation_estimate": asdict(estimate),
        "replication_estimate": asdict(estimate),
        "state": "PROMOTED",
        "promotion_state": "PROMOTED",
        "reason_codes": (),
        "limitations": (limitation,),
        "source_ledger_fingerprint": LEDGER_FP,
    }
    return GovernedPatternCandidate(
        pattern_id=payload["pattern_id"],
        domain=payload["domain"],
        statement=payload["statement"],
        discovery_population_id="D",
        validation_population_id="V",
        replication_population_id="R",
        discovery_estimate=estimate,
        validation_estimate=estimate,
        replication_estimate=estimate,
        state="PROMOTED",
        promotion_state="PROMOTED",
        reason_codes=(),
        limitations=(limitation,),
        source_ledger_fingerprint=LEDGER_FP,
        candidate_fingerprint=_hash(payload),
    )


def rule(domain="pricing"):
    return make_pattern_applicability_rule(
        rule_id="RULE-1",
        pattern_domain=domain,
        required_fact_keys=("phase",),
        required_assumption_keys=("candidate_list_price",),
        fact_equals={"phase": "C-1"},
    )


def assemble(**overrides):
    kwargs = {
        "scenario_contract": ready_contract(),
        "baseline_snapshot_id": "SNAPSHOT-1",
        "baseline_status": "CERTIFIED",
        "baseline_fingerprint": BASELINE_FP,
        "baseline_community_id": "SAN-TAN-HEIGHTS",
        "baseline_subject_id": "PROPERTY-1",
        "baseline_facts": {"phase": "C-1", "sqft": 2400},
        "baseline_fact_source_fingerprints": {"phase": SOURCE_FP, "sqft": "e" * 64},
        "promoted_patterns": (promoted_pattern(),),
        "applicability_rules": (rule(),),
        "registry": b_registry(),
        "unknowns": ("pool status not certified",),
        "limitations": ("baseline is a point-in-time certified state",),
    }
    kwargs.update(overrides)
    return assemble_certified_scenario_baseline(**kwargs)


def test_registry_is_frozen():
    registry = b_registry()
    assert registry["status"] == "FROZEN"
    assert registry["ticket"] == "M13-006B"
    assert registry["policy"]["no_scenario_calculation"] is True
    assert registry["policy"]["no_prediction"] is True
    assert registry["policy"]["no_recommendation"] is True
    assert registry["policy"]["no_ranking"] is True
    assert registry["policy"]["no_execution"] is True


def test_rule_hash_is_deterministic_and_order_independent():
    x = make_pattern_applicability_rule(
        rule_id="R", pattern_domain="pricing",
        required_fact_keys=("phase", "sqft"),
        required_assumption_keys=("candidate_list_price",),
        fact_equals={"phase": "C-1", "sqft": 2400},
    )
    y = make_pattern_applicability_rule(
        rule_id="R", pattern_domain="pricing",
        required_fact_keys=("sqft", "phase"),
        required_assumption_keys=("candidate_list_price",),
        fact_equals={"sqft": 2400, "phase": "C-1"},
    )
    assert x == y


def test_draft_scenario_contract_is_rejected():
    ar = load_scenario_governance_registry(A_REGISTRY)
    fact = make_scenario_fact(
        key="phase", value="C-1", source_artifact_id="SNAPSHOT-1", source_fingerprint=SOURCE_FP
    )
    assumption = make_scenario_assumption(
        key="candidate_list_price", assumption_type="MONEY", value=525000,
        source="HUMAN_EXPLICIT", registry=ar,
    )
    draft = build_scenario_contract(
        scenario_id="S", contract_version=1, community_id="SAN-TAN-HEIGHTS",
        subject_id="PROPERTY-1", baseline_snapshot_id="SNAPSHOT-1",
        baseline_status="CERTIFIED", baseline_fingerprint=BASELINE_FP,
        facts=(fact,), assumptions=(assumption,), policy_version="v1", registry=ar,
    )
    with pytest.raises(ValueError, match="READY"):
        assemble(scenario_contract=draft)


@pytest.mark.parametrize("key,value,match", [
    ("baseline_status", "DRAFT", "certified baseline"),
    ("baseline_snapshot_id", "OTHER", "identity mismatch"),
    ("baseline_fingerprint", "f" * 64, "fingerprint mismatch"),
    ("baseline_community_id", "OTHER", "community identity mismatch"),
    ("baseline_subject_id", "OTHER", "subject identity mismatch"),
])
def test_exact_baseline_binding_is_enforced(key, value, match):
    with pytest.raises(ValueError, match=match):
        assemble(**{key: value})


def test_scenario_fact_value_must_match_certified_baseline():
    with pytest.raises(ValueError, match="fact value mismatch"):
        assemble(baseline_facts={"phase": "B-3", "sqft": 2400})


def test_scenario_fact_source_lineage_must_match():
    with pytest.raises(ValueError, match="source lineage mismatch"):
        assemble(
            baseline_fact_source_fingerprints={"phase": "f" * 64, "sqft": "e" * 64}
        )


def test_unpromoted_pattern_is_rejected():
    p = promoted_pattern()
    bad = GovernedPatternCandidate(**{**asdict(p), "state": "REPLICATED", "promotion_state": "ELIGIBLE"})
    with pytest.raises(ValueError, match="promoted patterns only"):
        assemble(promoted_patterns=(bad,))


def test_applicable_pattern_preserves_statement_lineage_and_limitations():
    context = assemble()
    item = context.pattern_applicability[0]
    pattern = promoted_pattern()
    assert item.state == "APPLICABLE"
    assert item.pattern_statement == pattern.statement
    assert item.pattern_fingerprint == pattern.candidate_fingerprint
    assert item.source_ledger_fingerprint == LEDGER_FP
    assert "Historical association only." in item.limitations
    assert "Historical association only." in context.limitations


def test_missing_rule_is_explicit_unknown_not_silently_ignored():
    context = assemble(applicability_rules=())
    item = context.pattern_applicability[0]
    assert item.state == "UNKNOWN"
    assert item.reason_codes == ("NO_GOVERNED_APPLICABILITY_RULE",)
    assert any("NO_GOVERNED_APPLICABILITY_RULE" in x for x in context.unknowns)


def test_rule_value_mismatch_is_explicit_not_applicable():
    mismatch = make_pattern_applicability_rule(
        rule_id="RULE-1",
        pattern_domain="pricing",
        required_fact_keys=("phase",),
        fact_equals={"phase": "B-3"},
    )
    context = assemble(applicability_rules=(mismatch,))
    item = context.pattern_applicability[0]
    assert item.state == "NOT_APPLICABLE"
    assert "FACT_VALUE_MISMATCH:phase" in item.reason_codes


def test_missing_required_context_is_explicit_unknown():
    missing = make_pattern_applicability_rule(
        rule_id="RULE-1",
        pattern_domain="pricing",
        required_fact_keys=("pool",),
    )
    context = assemble(applicability_rules=(missing,))
    item = context.pattern_applicability[0]
    assert item.state == "UNKNOWN"
    assert "MISSING_FACT:pool" in item.reason_codes


def test_domain_rule_mismatch_is_not_applicable():
    item = assess_pattern_applicability(
        pattern=promoted_pattern(domain="pricing"),
        rule=rule(domain="buyer_depth"),
        facts={"phase": "C-1"},
        assumptions={"candidate_list_price": 525000},
        registry=b_registry(),
    )
    assert item.state == "NOT_APPLICABLE"
    assert "PATTERN_DOMAIN_RULE_MISMATCH" in item.reason_codes


def test_duplicate_rules_for_same_domain_are_rejected():
    with pytest.raises(ValueError, match="multiple applicability rules"):
        assemble(applicability_rules=(rule(), rule()))


def test_context_is_deterministic_and_replayable():
    x = assemble()
    y = assemble()
    assert x == y
    assert validate_certified_scenario_baseline_replay(
        x,
        scenario_contract=ready_contract(),
        baseline_status="CERTIFIED",
        baseline_community_id="SAN-TAN-HEIGHTS",
        baseline_subject_id="PROPERTY-1",
        baseline_facts={"phase": "C-1", "sqft": 2400},
        baseline_fact_source_fingerprints={"phase": SOURCE_FP, "sqft": "e" * 64},
        promoted_patterns=(promoted_pattern(),),
        applicability_rules=(rule(),),
        registry=b_registry(),
    )


def test_no_prediction_recommendation_ranking_or_execution_fields_exist():
    forbidden = {
        "prediction", "predicted_price", "sale_probability", "recommended_action",
        "recommended_price", "rank", "winner", "utility_score", "seller_score",
        "execute", "execution_state", "selected_price",
    }
    for cls in (PatternApplicabilityRule, PatternApplicability, CertifiedScenarioBaseline):
        assert {x.name for x in fields(cls)}.isdisjoint(forbidden)
