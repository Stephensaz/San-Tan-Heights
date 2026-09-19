from dataclasses import fields, replace

import pytest

from src.community_temporal_state.scenario_governance import (
    ScenarioAssumption,
    ScenarioContract,
    ScenarioFact,
    assert_ready_contract_immutable,
    build_scenario_contract,
    load_scenario_governance_registry,
    make_scenario_assumption,
    make_scenario_fact,
    ready_scenario_contract,
    validate_scenario_contract_replay,
)

REGISTRY = "registries/community_temporal_state/m13-006a-scenario-governance-v1.0.yaml"


def registry():
    return load_scenario_governance_registry(REGISTRY)


def fact(key="current_list_price", value=500000):
    return make_scenario_fact(
        key=key,
        value=value,
        source_artifact_id="SNAPSHOT-1",
        source_fingerprint="a" * 64,
    )


def assumption(key="candidate_list_price", assumption_type="MONEY", value=525000):
    return make_scenario_assumption(
        key=key,
        assumption_type=assumption_type,
        value=value,
        source="HUMAN_EXPLICIT",
        limitation="Scenario input only; not a recommendation.",
        registry=registry(),
    )


def contract(*, facts=(None,), assumptions=(None,), status="CERTIFIED", fp="b" * 64):
    fs = (fact(),) if facts == (None,) else facts
    ass = (assumption(),) if assumptions == (None,) else assumptions
    return build_scenario_contract(
        scenario_id="SCENARIO-1",
        contract_version=1,
        community_id="SAN-TAN-HEIGHTS",
        subject_id="PROPERTY-1",
        baseline_snapshot_id="SNAPSHOT-1",
        baseline_status=status,
        baseline_fingerprint=fp,
        facts=fs,
        assumptions=ass,
        policy_version="M13-006A-v1.0",
        registry=registry(),
    )


def test_contract_is_deterministic_and_order_independent():
    f1 = fact("bedrooms", 4)
    f2 = fact("sqft", 2400)
    a1 = assumption("candidate_list_price", "MONEY", 525000)
    a2 = assumption("seller_concession_percent", "PERCENT", 2.0)
    x = contract(facts=(f1, f2), assumptions=(a1, a2))
    y = contract(facts=(f2, f1), assumptions=(a2, a1))
    assert x.contract_fingerprint == y.contract_fingerprint
    assert validate_scenario_contract_replay(x)


def test_uncertified_baseline_is_rejected():
    with pytest.raises(ValueError, match="certified baseline"):
        contract(status="DRAFT")


def test_invalid_baseline_fingerprint_is_rejected():
    with pytest.raises(ValueError, match="lowercase sha256"):
        contract(fp="not-a-hash")


def test_typed_assumptions_are_enforced():
    with pytest.raises(ValueError, match="PERCENT"):
        assumption("seller_concession_percent", "PERCENT", 101)
    with pytest.raises(ValueError, match="INTEGER"):
        assumption("days", "INTEGER", 1.5)
    with pytest.raises(ValueError, match="unsupported"):
        assumption("x", "RANGE", 3)


def test_assumption_source_is_required():
    with pytest.raises(ValueError, match="source"):
        make_scenario_assumption(
            key="candidate_list_price",
            assumption_type="MONEY",
            value=525000,
            source="",
            registry=registry(),
        )


def test_fact_and_assumption_key_collision_is_rejected():
    with pytest.raises(ValueError, match="collision"):
        contract(
            facts=(fact("candidate_list_price", 500000),),
            assumptions=(assumption("candidate_list_price", "MONEY", 525000),),
        )


def test_duplicate_fact_and_assumption_keys_are_rejected():
    with pytest.raises(ValueError, match="duplicate fact"):
        contract(facts=(fact("sqft", 2400), fact("sqft", 2400)))
    with pytest.raises(ValueError, match="duplicate assumption"):
        contract(assumptions=(assumption("price"), assumption("price")))


def test_at_least_one_explicit_assumption_is_required():
    with pytest.raises(ValueError, match="at least one"):
        contract(assumptions=())


def test_ready_transition_is_deterministic_and_replayable():
    x = contract()
    r1 = ready_scenario_contract(x)
    r2 = ready_scenario_contract(x)
    assert r1.state == "READY"
    assert r1.contract_fingerprint == r2.contract_fingerprint
    assert validate_scenario_contract_replay(r1)


def test_ready_contract_cannot_transition_again_or_mutate():
    ready = ready_scenario_contract(contract())
    with pytest.raises(ValueError, match="only DRAFT"):
        ready_scenario_contract(ready)
    changed = replace(ready, policy_version="changed")
    with pytest.raises(ValueError, match="immutable"):
        assert_ready_contract_immutable(ready, changed)


def test_supersession_requires_new_version_and_valid_hash():
    old = ready_scenario_contract(contract())
    newer = build_scenario_contract(
        scenario_id="SCENARIO-1",
        contract_version=2,
        community_id="SAN-TAN-HEIGHTS",
        subject_id="PROPERTY-1",
        baseline_snapshot_id="SNAPSHOT-1",
        baseline_status="CERTIFIED",
        baseline_fingerprint="b" * 64,
        facts=(fact(),),
        assumptions=(assumption(value=515000),),
        policy_version="M13-006A-v1.0",
        registry=registry(),
        supersedes_scenario_fingerprint=old.contract_fingerprint,
    )
    assert newer.contract_version == 2
    assert newer.supersedes_scenario_fingerprint == old.contract_fingerprint
    assert newer.contract_fingerprint != old.contract_fingerprint


def test_tampered_contract_fails_replay():
    x = contract()
    assert validate_scenario_contract_replay(x)
    assert validate_scenario_contract_replay(replace(x, state="READY")) is False


def test_no_prediction_recommendation_ranking_or_execution_fields_exist():
    forbidden = {
        "prediction",
        "predicted_price",
        "sale_probability",
        "recommended_action",
        "recommended_price",
        "rank",
        "winner",
        "utility_score",
        "seller_score",
        "execute",
        "execution_state",
    }
    for cls in (ScenarioFact, ScenarioAssumption, ScenarioContract):
        assert set(x.name for x in fields(cls)).isdisjoint(forbidden)
