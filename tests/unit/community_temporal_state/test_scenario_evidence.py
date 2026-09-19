from dataclasses import fields
from datetime import datetime, timezone

import pytest

from src.community_temporal_state.history import TemporalLedger, make_temporal_entry
from src.community_temporal_state.scenario_evidence import (
    HistoricalEvidenceItem,
    HistoricalEvidenceRule,
    HistoricalEvidenceSet,
    load_historical_evidence_registry,
    make_historical_evidence_rule,
    retrieve_historical_evidence,
    validate_historical_evidence_replay,
)
from src.community_temporal_state.scenario_baseline import CertifiedScenarioBaseline

REGISTRY = "registries/community_temporal_state/m13-006c-historical-evidence-v1.0.yaml"
LEDGER_REGISTRY = "registries/community_temporal_state/m13-004-temporal-history-v1.0.yaml"


def registry():
    return load_historical_evidence_registry(REGISTRY)


def context():
    return CertifiedScenarioBaseline(
        scenario_id="SCENARIO-1",
        scenario_contract_fingerprint="a"*64,
        community_id="SAN-TAN-HEIGHTS",
        subject_id="PROPERTY-1",
        baseline_snapshot_id="SNAPSHOT-1",
        baseline_fingerprint="b"*64,
        facts=(("phase","C-1"),),
        fact_source_fingerprints=("c"*64,),
        assumptions=(("candidate_list_price",525000),),
        pattern_applicability=(),
        unknowns=(),
        limitations=("Historical patterns are descriptive only.",),
        context_fingerprint="d"*64,
    )


def ledger():
    import yaml
    r = yaml.safe_load(open(LEDGER_REGISTRY))
    e1 = make_temporal_entry(
        entry_id="E1", community_id="SAN-TAN-HEIGHTS", entry_type="SNAPSHOT",
        scope="PROPERTY", scope_id="P1", fact_key="buyer_depth", fact_value=4,
        valid_from="2026-01-01T00:00:00+00:00", known_at="2026-01-02T00:00:00+00:00",
        recorded_at="2026-01-02T00:00:00+00:00", registry=r,
        source_fingerprints=("1"*64,), evidence_fingerprints=("2"*64,),
        limitations=("Historical observation.",),
    )
    e2 = make_temporal_entry(
        entry_id="E2", community_id="SAN-TAN-HEIGHTS", entry_type="SNAPSHOT",
        scope="PROPERTY", scope_id="P2", fact_key="buyer_depth", fact_value=6,
        valid_from="2026-02-01T00:00:00+00:00", known_at="2026-02-02T00:00:00+00:00",
        recorded_at="2026-02-02T00:00:00+00:00", registry=r,
        source_fingerprints=("3"*64,), evidence_fingerprints=("4"*64,),
        limitations=("Historical observation.",),
    )
    e3 = make_temporal_entry(
        entry_id="E3", community_id="SAN-TAN-HEIGHTS", entry_type="SNAPSHOT",
        scope="PROPERTY", scope_id="P3", fact_key="pricing_position", fact_value=0.98,
        valid_from="2026-03-01T00:00:00+00:00", known_at="2026-03-05T00:00:00+00:00",
        recorded_at="2026-03-05T00:00:00+00:00", registry=r,
        source_fingerprints=("5"*64,), evidence_fingerprints=("6"*64,),
    )
    from src.community_temporal_state.history import build_temporal_ledger
    return build_temporal_ledger(
        ledger_id="L1", community_id="SAN-TAN-HEIGHTS", entries=(e1,e2,e3)
    )


def rule(**kwargs):
    data = dict(
        rule_id="R1", scope="PROPERTY",
        fact_keys=("buyer_depth",), truth_states=("ASSERTED",),
        minimum_items=2, maximum_items=10,
    )
    data.update(kwargs)
    return make_historical_evidence_rule(**data)


def test_registry_is_frozen():
    r = registry()
    assert r["status"] == "FROZEN"
    assert r["ticket"] == "M13-006C"
    assert r["policy"]["no_scenario_calculation"] is True
    assert r["policy"]["no_prediction"] is True
    assert r["policy"]["no_recommendation"] is True
    assert r["policy"]["no_ranking"] is True
    assert r["policy"]["no_execution"] is True


def test_rule_is_deterministic_and_order_independent():
    x = make_historical_evidence_rule(
        rule_id="R", scope="PROPERTY", fact_keys=("b","a"),
        truth_states=("ASSERTED","CORRECTED"), minimum_items=1, maximum_items=5
    )
    y = make_historical_evidence_rule(
        rule_id="R", scope="PROPERTY", fact_keys=("a","b"),
        truth_states=("CORRECTED","ASSERTED"), minimum_items=1, maximum_items=5
    )
    assert x == y


@pytest.mark.parametrize("minimum,maximum", [(-1,1),(2,1),(0,0)])
def test_invalid_rule_bounds_rejected(minimum, maximum):
    with pytest.raises(ValueError, match="bounds"):
        make_historical_evidence_rule(
            rule_id="R", scope="PROPERTY", fact_keys=("x",),
            truth_states=("ASSERTED",), minimum_items=minimum, maximum_items=maximum
        )


def test_invalid_time_window_rejected():
    with pytest.raises(ValueError, match="valid_to"):
        make_historical_evidence_rule(
            rule_id="R", scope="PROPERTY", fact_keys=("x",), truth_states=("ASSERTED",),
            minimum_items=1, maximum_items=2,
            valid_from="2026-03-01T00:00:00+00:00",
            valid_to="2026-02-01T00:00:00+00:00",
        )


def test_retrieval_is_deterministic():
    x = retrieve_historical_evidence(
        evidence_set_id="S1", context=context(), ledger=ledger(), rule=rule(), registry=registry()
    )
    y = retrieve_historical_evidence(
        evidence_set_id="S1", context=context(), ledger=ledger(), rule=rule(), registry=registry()
    )
    assert x == y
    assert x.coverage_state == "SUFFICIENT"
    assert tuple(i.entry_id for i in x.items) == ("E1","E2")


def test_valid_time_filter_is_enforced():
    x = retrieve_historical_evidence(
        evidence_set_id="S1", context=context(), ledger=ledger(),
        rule=rule(valid_from="2026-02-01T00:00:00+00:00"), registry=registry()
    )
    assert tuple(i.entry_id for i in x.items) == ("E2",)
    assert x.coverage_state == "PARTIAL"


def test_knowledge_time_filter_blocks_future_knowledge():
    x = retrieve_historical_evidence(
        evidence_set_id="S1", context=context(), ledger=ledger(),
        rule=rule(known_by="2026-01-15T00:00:00+00:00"), registry=registry()
    )
    assert tuple(i.entry_id for i in x.items) == ("E1",)


def test_unrequested_fact_is_not_selected():
    x = retrieve_historical_evidence(
        evidence_set_id="S1", context=context(), ledger=ledger(), rule=rule(), registry=registry()
    )
    assert all(i.fact_key == "buyer_depth" for i in x.items)


def test_maximum_items_is_deterministic_and_uses_latest_matching_rows():
    x = retrieve_historical_evidence(
        evidence_set_id="S1", context=context(), ledger=ledger(),
        rule=rule(minimum_items=1, maximum_items=1), registry=registry()
    )
    assert tuple(i.entry_id for i in x.items) == ("E2",)


def test_missing_requested_fact_is_explicit_partial():
    x = retrieve_historical_evidence(
        evidence_set_id="S1", context=context(), ledger=ledger(),
        rule=make_historical_evidence_rule(
            rule_id="R", scope="PROPERTY",
            fact_keys=("buyer_depth","nonexistent"), truth_states=("ASSERTED",),
            minimum_items=1, maximum_items=10,
        ), registry=registry()
    )
    assert x.coverage_state == "PARTIAL"
    assert x.missing_fact_keys == ("nonexistent",)
    assert any("incomplete" in s for s in x.limitations)


def test_empty_result_is_explicit_none():
    x = retrieve_historical_evidence(
        evidence_set_id="S1", context=context(), ledger=ledger(),
        rule=make_historical_evidence_rule(
            rule_id="R", scope="COMMUNITY", fact_keys=("buyer_depth",),
            truth_states=("ASSERTED",), minimum_items=1, maximum_items=10,
        ), registry=registry()
    )
    assert x.coverage_state == "NONE"
    assert x.items == ()
    assert any("No governed historical evidence" in s for s in x.limitations)


def test_entry_lineage_truth_state_and_limitations_are_preserved():
    x = retrieve_historical_evidence(
        evidence_set_id="S1", context=context(), ledger=ledger(), rule=rule(), registry=registry()
    )
    item = x.items[0]
    assert item.truth_state == "ASSERTED"
    assert item.source_fingerprints == ("1"*64,)
    assert item.evidence_fingerprints == ("2"*64,)
    assert "Historical observation." in item.limitations
    assert item.entry_fingerprint


def test_context_limitations_are_carried_forward():
    x = retrieve_historical_evidence(
        evidence_set_id="S1", context=context(), ledger=ledger(), rule=rule(), registry=registry()
    )
    assert "Historical patterns are descriptive only." in x.limitations


def test_replay_is_exact():
    c=context(); l=ledger(); r=rule(); reg=registry()
    x=retrieve_historical_evidence(evidence_set_id="S1",context=c,ledger=l,rule=r,registry=reg)
    assert validate_historical_evidence_replay(x,context=c,ledger=l,rule=r,registry=reg)


def test_no_decision_prediction_ranking_or_execution_fields_exist():
    forbidden={
        "prediction","predicted_price","sale_probability","recommended_action","recommended_price",
        "rank","winner","utility_score","seller_score","execute","execution_state","selected_price"
    }
    for cls in (HistoricalEvidenceRule,HistoricalEvidenceItem,HistoricalEvidenceSet):
        assert {x.name for x in fields(cls)}.isdisjoint(forbidden)
