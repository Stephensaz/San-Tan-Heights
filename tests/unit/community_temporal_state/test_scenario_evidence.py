from dataclasses import fields, replace

import pytest

from src.community_temporal_state.history import (
    build_temporal_ledger,
    load_temporal_history_registry,
    make_temporal_entry,
)
from src.community_temporal_state.scenario_baseline import CertifiedScenarioBaseline
from src.community_temporal_state.scenario_evidence import (
    ScenarioEvidenceQuery,
    ScenarioEvidenceRecord,
    ScenarioEvidenceSet,
    build_scenario_evidence_query,
    load_scenario_evidence_registry,
    retrieve_scenario_evidence,
    validate_scenario_evidence_replay,
)

C_REGISTRY = "registries/community_temporal_state/m13-006c-scenario-evidence-v1.0.yaml"
H_REGISTRY = "registries/community_temporal_state/m13-004-temporal-history-v1.0.yaml"


def c_registry():
    return load_scenario_evidence_registry(C_REGISTRY)


def context():
    return CertifiedScenarioBaseline(
        scenario_id="SCENARIO-1",
        scenario_contract_fingerprint="a" * 64,
        community_id="SAN-TAN-HEIGHTS",
        subject_id="PROPERTY-1",
        baseline_snapshot_id="SNAPSHOT-1",
        baseline_fingerprint="b" * 64,
        facts=(("phase", "C-1"),),
        fact_source_fingerprints=("c" * 64,),
        assumptions=(("candidate_list_price", 525000),),
        pattern_applicability=(),
        unknowns=(),
        limitations=("Certified point-in-time context.",),
        context_fingerprint="d" * 64,
    )


def entry(
    entry_id,
    *,
    scope="PROPERTY",
    scope_id="PROPERTY-1",
    fact_key="pricing_position",
    value=100,
    valid_from="2026-07-01T12:00:00-07:00",
    known_at="2026-07-02T12:00:00-07:00",
    truth_state="ASSERTED",
    previous=None,
    limitations=(),
    sources=("e" * 64,),
):
    return make_temporal_entry(
        entry_id=entry_id,
        community_id="SAN-TAN-HEIGHTS",
        entry_type="CORRECTION" if previous else "DELTA",
        scope=scope,
        scope_id=scope_id,
        fact_key=fact_key,
        fact_value=value,
        valid_from=valid_from,
        known_at=known_at,
        recorded_at=known_at,
        truth_state=truth_state,
        source_fingerprints=sources,
        previous_entry_fingerprint=previous,
        evidence_fingerprints=("f" * 64,),
        limitations=limitations,
        registry=load_temporal_history_registry(H_REGISTRY),
    )


def ledger(entries=None):
    rows = entries or (
        entry("E1"),
        entry(
            "E2",
            scope="COMMUNITY",
            scope_id="SAN-TAN-HEIGHTS",
            fact_key="buyer_depth",
            value=4,
            valid_from="2026-08-01T12:00:00-07:00",
            known_at="2026-08-02T12:00:00-07:00",
        ),
    )
    return build_temporal_ledger(
        ledger_id="LEDGER-1",
        community_id="SAN-TAN-HEIGHTS",
        entries=rows,
    )


def query(**overrides):
    kwargs = dict(
        query_id="Q1",
        context=context(),
        scopes=("PROPERTY", "COMMUNITY"),
        fact_keys=("pricing_position", "buyer_depth"),
        valid_from="2026-06-01T00:00:00-07:00",
        valid_to="2026-09-01T00:00:00-07:00",
        knowledge_cutoff="2026-09-01T00:00:00-07:00",
        registry=c_registry(),
    )
    kwargs.update(overrides)
    return build_scenario_evidence_query(**kwargs)


def retrieve(**overrides):
    kwargs = dict(
        evidence_set_id="SET-1",
        context=context(),
        ledger=ledger(),
        query=query(),
        registry=c_registry(),
    )
    kwargs.update(overrides)
    return retrieve_scenario_evidence(**kwargs)


def test_registry_frozen_and_boundaries():
    r = c_registry()
    assert r["status"] == "FROZEN"
    assert r["ticket"] == "M13-006C"
    for key in ("no_prediction", "no_causal_inference", "no_recommendation", "no_ranking", "no_scenario_calculation", "no_execution"):
        assert r["policy"][key] is True


def test_query_is_deterministic_and_order_independent():
    a = query(scopes=("COMMUNITY", "PROPERTY"), fact_keys=("buyer_depth", "pricing_position"))
    b = query(scopes=("PROPERTY", "COMMUNITY"), fact_keys=("pricing_position", "buyer_depth"))
    assert a == b


def test_query_requires_explicit_fact_keys():
    with pytest.raises(ValueError, match="explicit fact keys"):
        query(fact_keys=())


def test_query_rejects_ungoverned_scope():
    with pytest.raises(ValueError, match="explicit and governed"):
        query(scopes=("SECRET",))


def test_query_requires_valid_time_order():
    with pytest.raises(ValueError, match="valid_to"):
        query(
            valid_from="2026-09-01T00:00:00-07:00",
            valid_to="2026-08-01T00:00:00-07:00",
        )


def test_matching_history_is_included_with_lineage():
    result = retrieve()
    assert [x.entry_id for x in result.included] == ["E1", "E2"]
    assert all(x.state == "INCLUDED" for x in result.included)
    assert result.source_fingerprints == ("e" * 64,)
    assert result.evidence_fingerprints == ("f" * 64,)
    assert "does not predict future outcomes" in result.limitations[-1]


def test_future_knowledge_is_explicitly_excluded():
    future = entry(
        "FUTURE",
        known_at="2026-09-15T12:00:00-07:00",
        valid_from="2026-08-15T12:00:00-07:00",
    )
    result = retrieve(
        ledger=ledger((entry("E1"), future)),
        query=query(knowledge_cutoff="2026-09-01T00:00:00-07:00"),
    )
    row = next(x for x in result.excluded if x.entry_id == "FUTURE")
    assert "KNOWN_AFTER_CUTOFF" in row.reason_codes


def test_outside_valid_window_is_explicitly_excluded():
    old = entry("OLD", valid_from="2025-01-01T12:00:00-07:00", known_at="2025-01-02T12:00:00-07:00")
    result = retrieve(ledger=ledger((old,)))
    assert result.included == ()
    assert "OUTSIDE_VALID_TIME_WINDOW" in result.excluded[0].reason_codes
    assert "NO_HISTORICAL_EVIDENCE_MATCHED_GOVERNED_QUERY" in result.unknowns


def test_other_property_is_excluded():
    other = entry("OTHER", scope_id="PROPERTY-2")
    result = retrieve(ledger=ledger((other,)))
    assert "SUBJECT_MISMATCH" in result.excluded[0].reason_codes


def test_unrequested_fact_key_is_excluded():
    other = entry("OTHER", fact_key="garage_count")
    result = retrieve(ledger=ledger((other,)))
    assert "FACT_KEY_NOT_REQUESTED" in result.excluded[0].reason_codes


def test_subject_history_can_be_disabled():
    result = retrieve(query=query(include_subject_history=False))
    property_row = next(x for x in result.excluded if x.entry_id == "E1")
    assert "SUBJECT_HISTORY_DISABLED" in property_row.reason_codes


def test_community_history_can_be_disabled():
    result = retrieve(query=query(include_community_history=False))
    community_row = next(x for x in result.excluded if x.entry_id == "E2")
    assert "COMMUNITY_HISTORY_DISABLED" in community_row.reason_codes


def test_correction_lineage_is_preserved():
    original = entry("E1")
    correction = entry(
        "E1-CORR",
        value=98,
        valid_from="2026-07-03T12:00:00-07:00",
        known_at="2026-07-04T12:00:00-07:00",
        truth_state="CORRECTED",
        previous=original.entry_fingerprint,
    )
    result = retrieve(ledger=ledger((original, correction)))
    corrected = next(x for x in result.included if x.entry_id == "E1-CORR")
    assert corrected.previous_entry_fingerprint == original.entry_fingerprint


def test_entry_limitations_are_carried_forward():
    limited = entry("LIMITED", limitations=("EFFECTIVE_TIME_ESTIMATED",))
    result = retrieve(ledger=ledger((limited,)))
    assert "EFFECTIVE_TIME_ESTIMATED" in result.limitations


def test_context_fingerprint_mismatch_is_rejected():
    q = query()
    bad = replace(q, scenario_context_fingerprint="9" * 64)
    with pytest.raises(ValueError, match="context fingerprint mismatch"):
        retrieve(query=bad)


def test_nonreproducible_ledger_is_rejected():
    l = ledger()
    bad = replace(l, ledger_fingerprint="0" * 64)
    with pytest.raises(ValueError, match="reproducible temporal ledger"):
        retrieve(ledger=bad)


def test_result_is_deterministic_and_replayable():
    result = retrieve()
    assert result == retrieve()
    assert validate_scenario_evidence_replay(
        result,
        context=context(),
        ledger=ledger(),
        query=query(),
        registry=c_registry(),
    )


def test_no_prediction_recommendation_ranking_or_execution_fields_exist():
    forbidden = {
        "prediction", "predicted_price", "sale_probability", "recommended_action",
        "recommended_price", "rank", "winner", "utility_score", "seller_score",
        "execute", "execution_state", "selected_price", "causal_effect",
    }
    for cls in (ScenarioEvidenceQuery, ScenarioEvidenceRecord, ScenarioEvidenceSet):
        assert {x.name for x in fields(cls)}.isdisjoint(forbidden)
