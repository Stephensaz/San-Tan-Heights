from dataclasses import fields, replace

import pytest

from src.community_temporal_state.history import build_temporal_ledger, make_temporal_entry, load_temporal_history_registry
from src.community_temporal_state.patterns import (
    build_pattern_population,
    discover_pattern,
    load_evolution_pattern_registry,
    make_pattern_observation,
    promote_pattern,
    validate_and_replicate_pattern,
    validate_candidate_replay,
)

HR="registries/community_temporal_state/m13-004-temporal-history-v1.0.yaml"
PR="registries/community_temporal_state/m13-005-evolution-patterns-v1.0.yaml"


def hr(): return load_temporal_history_registry(HR)
def pr(): return load_evolution_pattern_registry(PR)


def ledger():
    e=make_temporal_entry(
        entry_id="E-1", community_id="SAN-TAN-HEIGHTS", entry_type="SNAPSHOT",
        scope="PROPERTY", scope_id="P-1", fact_key="sample", fact_value={"ok":True},
        valid_from="2026-01-01T00:00:00-07:00", known_at="2026-01-01T00:01:00-07:00",
        recorded_at="2026-01-01T00:02:00-07:00", registry=hr(),
        source_fingerprints=("a"*64,), evidence_fingerprints=("a"*64,),
    )
    return build_temporal_ledger(ledger_id="L-1", community_id="SAN-TAN-HEIGHTS", entries=(e,))


def obs(prefix, start, count, slope=1.0, regime="R1"):
    out=[]
    source=ledger().entries[0].entry_fingerprint
    for i in range(count):
        x=float(start+i)
        y=slope*x
        out.append(make_pattern_observation(
            observation_id=f"{prefix}-{i}", property_id=f"P-{prefix}-{i}",
            period_id=f"T-{i%2}", regime_id=regime,
            exposure_value=x, outcome_value=y,
            confounder_values={"phase":"A","size_band":"MID"},
            source_entry_fingerprints=(source,),
        ))
    return out


def pop(pid, role, rows):
    return build_pattern_population(
        population_id=pid, role=role, domain="BUYER_DEPTH",
        inclusion_rule="frozen:v1", observations=rows, regime_ids=("R1",),
        confounder_manifest=("phase","size_band"), registry=pr(),
    )


def test_population_is_deterministic_and_lineage_bound():
    rows=obs("D",0,8)
    a=pop("PD","DISCOVERY",rows)
    b=pop("PD","DISCOVERY",rows)
    assert a.population_fingerprint==b.population_fingerprint
    assert a.source_entry_fingerprints


def test_discovery_requires_temporal_lineage():
    with pytest.raises(ValueError,match="temporal lineage"):
        make_pattern_observation(
            observation_id="X", property_id="P", period_id="T", regime_id="R1",
            exposure_value=1, outcome_value=1, confounder_values={"phase":"A"},
            source_entry_fingerprints=(),
        )


def test_null_result_is_preserved_not_promoted():
    rows=obs("D",0,8,slope=0.0)
    p=pop("PD","DISCOVERY",rows)
    c=discover_pattern(
        pattern_id="PAT-1", domain="BUYER_DEPTH",
        statement="Historical association test", discovery_population=p,
        observations=rows, ledger=ledger(), registry=pr(),
    )
    assert c.state=="NULL_RESULT"
    assert c.promotion_state=="INELIGIBLE"
    assert "NULL_EFFECT" in c.reason_codes


def test_small_discovery_population_fails_closed():
    rows=obs("D",0,4)
    p=pop("PD","DISCOVERY",rows)
    c=discover_pattern(
        pattern_id="PAT-1", domain="BUYER_DEPTH", statement="Historical association test",
        discovery_population=p, observations=rows, ledger=ledger(), registry=pr(),
    )
    assert c.state=="NOT_ELIGIBLE"
    assert "DISCOVERY_SAMPLE_BELOW_MINIMUM" in c.reason_codes


def test_independent_validation_and_replication_can_become_eligible():
    d=obs("D",0,8,1.0)
    v=obs("V",20,6,1.0)
    r=obs("R",40,6,1.0)
    all_rows=d+v+r
    pd,pv,prp=pop("PD","DISCOVERY",d),pop("PV","VALIDATION",v),pop("PR","REPLICATION",r)
    c=discover_pattern(
        pattern_id="PAT-1", domain="BUYER_DEPTH", statement="Historical association test",
        discovery_population=pd, observations=all_rows, ledger=ledger(), registry=pr(),
    )
    x=validate_and_replicate_pattern(
        candidate=c, discovery_population=pd, validation_population=pv,
        replication_population=prp, observations=all_rows, ledger=ledger(), registry=pr(),
    )
    assert x.state=="REPLICATED"
    assert x.promotion_state=="ELIGIBLE"


def test_population_overlap_is_rejected():
    d=obs("D",0,8,1.0)
    v=d[:6]
    r=obs("R",40,6,1.0)
    pd,pv,prp=pop("PD","DISCOVERY",d),pop("PV","VALIDATION",v),pop("PR","REPLICATION",r)
    c=discover_pattern(
        pattern_id="PAT-1", domain="BUYER_DEPTH", statement="Historical association test",
        discovery_population=pd, observations=d+r, ledger=ledger(), registry=pr(),
    )
    with pytest.raises(ValueError,match="leakage"):
        validate_and_replicate_pattern(
            candidate=c, discovery_population=pd, validation_population=pv,
            replication_population=prp, observations=d+r, ledger=ledger(), registry=pr(),
        )


def test_failed_replication_is_preserved():
    d=obs("D",0,8,1.0)
    v=obs("V",20,6,1.0)
    r=obs("R",40,6,-1.0)
    all_rows=d+v+r
    pd,pv,prp=pop("PD","DISCOVERY",d),pop("PV","VALIDATION",v),pop("PR","REPLICATION",r)
    c=discover_pattern(
        pattern_id="PAT-1", domain="BUYER_DEPTH", statement="Historical association test",
        discovery_population=pd, observations=all_rows, ledger=ledger(), registry=pr(),
    )
    x=validate_and_replicate_pattern(
        candidate=c, discovery_population=pd, validation_population=pv,
        replication_population=prp, observations=all_rows, ledger=ledger(), registry=pr(),
    )
    assert x.state=="REPLICATION_FAILED"
    assert x.promotion_state=="INELIGIBLE"
    assert "EFFECT_DIRECTION_NOT_REPLICATED" in x.reason_codes


def test_only_replicated_pattern_can_be_promoted():
    d=obs("D",0,8,1.0)
    pd=pop("PD","DISCOVERY",d)
    c=discover_pattern(
        pattern_id="PAT-1", domain="BUYER_DEPTH", statement="Historical association test",
        discovery_population=pd, observations=d, ledger=ledger(), registry=pr(),
    )
    with pytest.raises(ValueError,match="not eligible"):
        promote_pattern(c,ledger=ledger())


def test_promoted_pattern_is_replayable():
    d=obs("D",0,8,1.0); v=obs("V",20,6,1.0); r=obs("R",40,6,1.0)
    all_rows=d+v+r
    pd,pv,prp=pop("PD","DISCOVERY",d),pop("PV","VALIDATION",v),pop("PR","REPLICATION",r)
    c=discover_pattern(pattern_id="PAT-1",domain="BUYER_DEPTH",statement="Historical association test",
        discovery_population=pd,observations=all_rows,ledger=ledger(),registry=pr())
    x=validate_and_replicate_pattern(candidate=c,discovery_population=pd,validation_population=pv,
        replication_population=prp,observations=all_rows,ledger=ledger(),registry=pr())
    promoted=promote_pattern(x,ledger=ledger())
    assert promoted.state=="PROMOTED"
    assert promoted.promotion_state=="PROMOTED"
    assert validate_candidate_replay(promoted)


def test_tampered_candidate_fails_replay():
    d=obs("D",0,8,1.0)
    pd=pop("PD","DISCOVERY",d)
    c=discover_pattern(pattern_id="PAT-1",domain="BUYER_DEPTH",statement="Historical association test",
        discovery_population=pd,observations=d,ledger=ledger(),registry=pr())
    assert validate_candidate_replay(c)
    assert validate_candidate_replay(replace(c,state="PROMOTED")) is False


def test_no_prediction_recommendation_or_ranking_fields_exist():
    forbidden={"prediction","recommended_action","recommended_price","rank","winner","utility_score","seller_score"}
    for cls in (type(make_pattern_observation(
        observation_id="X",property_id="P",period_id="T",regime_id="R1",
        exposure_value=1,outcome_value=1,confounder_values={"phase":"A"},
        source_entry_fingerprints=(ledger().entries[0].entry_fingerprint,),
    )), type(pop("PD","DISCOVERY",obs("D",0,8))),):
        assert set(x.name for x in fields(cls)).isdisjoint(forbidden)
