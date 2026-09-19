from dataclasses import fields, replace
import pytest

from src.community_temporal_state.scenario_explainability import ScenarioExplanation, ComparisonExplanation
from src.community_temporal_state.scenario_presentation_contracts import (
    ScenarioPresentationContract, ComparisonPresentationContract,
    build_scenario_presentation_contract, build_comparison_presentation_contract,
    load_presentation_contract_registry, validate_scenario_presentation_replay,
    validate_comparison_presentation_replay, validate_semantic_equivalence,
    assert_seller_payload_isolated,
)

REG="registries/community_temporal_state/m13-006i-presentation-contracts-v1.0.yaml"


def reg(): return load_presentation_contract_registry(REG)


def sx():
    return ScenarioExplanation(
        scenario_id="S1",
        scenario_context_fingerprint="a"*64,
        comparison_member_fingerprint="b"*64,
        facts=(("reference_price",500000),("internal_agent_note","AGENT_ONLY_SENTINEL")),
        assumptions=(("candidate_list_price",525000),("internal_agent_assumption","AGENT_ONLY_SENTINEL")),
        modeled_dimensions=("pricing_position","buyer_depth"),
        changed_from_reference=("pricing_position",),
        evidence_source_fingerprints=("c"*64,),
        evidence_fingerprints=("d"*64,),
        applicable_pattern_ids=("P1",),
        unknown_pattern_ids=("P2",),
        unknowns=("pool status unknown",),
        limitations=("Historical evidence descriptive only.",),
        explanation_fingerprint="e"*64,
    )


def cx():
    return ComparisonExplanation(
        comparison_id="C1",
        comparison_fingerprint="f"*64,
        scenario_ids=("S1","S2"),
        scenario_explanation_fingerprints=("e"*64,"1"*64),
        pairwise_differences=(("S1","S2","pricing_position","ABOVE","BELOW","DIFFERENT"),),
        unknowns=("buyer depth incomplete",),
        limitations=("Pairwise differences do not establish preference.",),
        explanation_fingerprint="2"*64,
    )


def test_registry_frozen_and_tiers():
    r=reg()
    assert r["status"]=="FROZEN"
    assert r["ticket"]=="M13-006I"
    assert r["tiers"]==["AGENT","SELLER"]


def test_agent_contract_preserves_full_detail():
    c=build_scenario_presentation_contract(contract_id="A1",tier="AGENT",explanation=sx(),registry=reg())
    sec={x.section_id:x for x in c.sections}
    assert sec["FACTS"].visibility=="FULL"
    assert ("internal_agent_note","AGENT_ONLY_SENTINEL") in sec["FACTS"].content
    assert sec["EVIDENCE_LINEAGE"].visibility=="FULL"


def test_seller_contract_physically_excludes_agent_only_fields():
    c=build_scenario_presentation_contract(contract_id="S1",tier="SELLER",explanation=sx(),registry=reg())
    sec={x.section_id:x for x in c.sections}
    assert ("internal_agent_note","AGENT_ONLY_SENTINEL") not in sec["FACTS"].content
    assert ("internal_agent_assumption","AGENT_ONLY_SENTINEL") not in sec["ASSUMPTIONS"].content
    assert sec["EVIDENCE_LINEAGE"].visibility=="SUPPRESSED"
    assert sec["EVIDENCE_LINEAGE"].content==()
    assert sec["EVIDENCE_LINEAGE"].suppression_reason
    assert_seller_payload_isolated(c)


def test_unknowns_limitations_and_disclosures_survive_seller_simplification():
    a=build_scenario_presentation_contract(contract_id="A",tier="AGENT",explanation=sx(),registry=reg())
    s=build_scenario_presentation_contract(contract_id="S",tier="SELLER",explanation=sx(),registry=reg())
    sa={x.section_id:x for x in a.sections}
    ss={x.section_id:x for x in s.sections}
    for key in ("UNKNOWNS","LIMITATIONS","DISCLOSURES","CHANGED_FROM_REFERENCE"):
        assert sa[key].content==ss[key].content
    assert validate_semantic_equivalence(agent=a,seller=s)


def test_comparison_contract_preserves_exact_pairwise_values():
    a=build_comparison_presentation_contract(contract_id="A",tier="AGENT",explanation=cx(),registry=reg())
    s=build_comparison_presentation_contract(contract_id="S",tier="SELLER",explanation=cx(),registry=reg())
    am={x.section_id:x for x in a.sections}
    sm={x.section_id:x for x in s.sections}
    assert am["COMPARISON_DIFFERENCES"].content==sm["COMPARISON_DIFFERENCES"].content
    assert sm["EVIDENCE_LINEAGE"].visibility=="SUPPRESSED"


def test_screen_and_export_eligibility_are_separate_fields():
    c=build_scenario_presentation_contract(contract_id="A",tier="AGENT",explanation=sx(),registry=reg())
    assert isinstance(c.screen_eligible,bool)
    assert isinstance(c.export_eligible,bool)


def test_scenario_contract_is_deterministic_and_replayable():
    c=build_scenario_presentation_contract(contract_id="A",tier="SELLER",explanation=sx(),registry=reg())
    assert validate_scenario_presentation_replay(c,explanation=sx(),registry=reg())


def test_comparison_contract_is_deterministic_and_replayable():
    c=build_comparison_presentation_contract(contract_id="A",tier="SELLER",explanation=cx(),registry=reg())
    assert validate_comparison_presentation_replay(c,explanation=cx(),registry=reg())


def test_tampered_scenario_contract_fails_replay():
    c=build_scenario_presentation_contract(contract_id="A",tier="SELLER",explanation=sx(),registry=reg())
    bad=replace(c,required_disclosures=("tampered",))
    assert not validate_scenario_presentation_replay(bad,explanation=sx(),registry=reg())


def test_unsupported_tier_fails_closed():
    with pytest.raises(ValueError,match="unsupported presentation tier"):
        build_scenario_presentation_contract(contract_id="X",tier="PUBLIC",explanation=sx(),registry=reg())


def test_seller_isolation_rejects_non_seller_contract():
    c=build_scenario_presentation_contract(contract_id="A",tier="AGENT",explanation=sx(),registry=reg())
    with pytest.raises(ValueError,match="SELLER"):
        assert_seller_payload_isolated(c)


def test_semantic_equivalence_detects_qualifier_loss():
    a=build_scenario_presentation_contract(contract_id="A",tier="AGENT",explanation=sx(),registry=reg())
    s=build_scenario_presentation_contract(contract_id="S",tier="SELLER",explanation=sx(),registry=reg())
    sec=list(s.sections)
    i=next(i for i,x in enumerate(sec) if x.section_id=="LIMITATIONS")
    sec[i]=replace(sec[i],content=())
    bad=replace(s,sections=tuple(sec))
    assert not validate_semantic_equivalence(agent=a,seller=bad)


def test_no_recommendation_ranking_prediction_or_render_fields():
    forbidden={"rank","winner","score","utility_score","recommended_action","recommended_scenario","prediction","confidence","rendered_html","pdf_bytes","execution_state"}
    for cls in (ScenarioPresentationContract,ComparisonPresentationContract):
        assert {x.name for x in fields(cls)}.isdisjoint(forbidden)
