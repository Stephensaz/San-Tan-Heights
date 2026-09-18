from dataclasses import fields

import pytest

from src.seller_intelligence.opportunity import (
    GovernedAlternativeInput, build_seller_opportunity, load_seller_opportunity_registry,
)
from src.seller_intelligence.strategy import (
    GovernedStrategyFinding, build_property_seller_strategy, load_seller_strategy_registry,
)
from src.seller_intelligence.scenario import (
    ScenarioAssumption, evaluate_seller_scenario, load_seller_scenario_registry,
)
from src.seller_intelligence.timeline import (
    GovernedTimelineSnapshot, build_seller_decision_timeline, load_seller_timeline_registry,
)
from src.seller_intelligence.communication import (
    translate_seller_intelligence, load_communication_registry,
)

O="registries/seller_intelligence/m11-001-seller-opportunity-v1.0.yaml"
S="registries/seller_intelligence/m11-002-property-seller-strategy-v1.0.yaml"
SC="registries/seller_intelligence/m11-003-seller-scenario-sensitivity-v1.0.yaml"
T="registries/seller_intelligence/m11-004-seller-decision-timeline-v1.0.yaml"
C="registries/seller_intelligence/m11-005-communication-translation-v1.0.yaml"

FP1="a"*64
FP2="b"*64
FP3="c"*64
FP4="d"*64


def build_inputs(*, with_scenario=True, missing_week=False, changed=True):
    alternatives=[
        GovernedAlternativeInput(
            alternative_id=f"A-{i}",subject_property_id="SUBJECT-1",alternative_property_id=f"P-{i}",
            alternative_type="CLOSE_SUBSTITUTE" if i<=5 else "BUILDER_ALTERNATIVE",
            baseline_certified=True,qa_status="PASS",output_tier="SELLER",freshness_state="CURRENT",
            evidence_fingerprint=f"{i:064x}",
        ) for i in range(1,8)
    ]
    opp=build_seller_opportunity(
        subject_property_id="SUBJECT-1",alternatives=alternatives,
        registry=load_seller_opportunity_registry(O),
    )
    rows=[
        ("BUYER_DEPTH","THIN"),("VERIFIED_DIFFERENTIATION","LIMITED"),
        ("NEW_CONSTRUCTION_PRESSURE","HIGH"),("PRICING_RESPONSE_ENVIRONMENT","WEAK"),
    ]
    if not missing_week:
        rows.append(("WEEK_OVER_WEEK_DIRECTION","WORSENING"))
    findings=[
        GovernedStrategyFinding(
            finding_id=f"F-{i}",subject_property_id="SUBJECT-1",dimension=d,state=s,
            summary=f"Governed {d} summary",baseline_certified=True,qa_status="PASS",
            output_tier="SELLER",freshness_state="CURRENT",evidence_fingerprint=f"{100+i:064x}",
        ) for i,(d,s) in enumerate(rows,1)
    ]
    strategy=build_property_seller_strategy(
        opportunity=opp,m11_001_certified=True,m11_001_evidence_fingerprint=FP1,
        findings=findings,registry=load_seller_strategy_registry(S),
    )
    scenario=None
    if with_scenario:
        scenario=evaluate_seller_scenario(
            scenario_id="SC-1",strategy=strategy,m11_002_certified=True,m11_002_evidence_fingerprint=FP2,
            assumptions=[ScenarioAssumption(
                assumption_id="H-1",subject_property_id="SUBJECT-1",target="BUYER_DEPTH",
                hypothetical_state="DEEP",rationale="What if buyer depth improves",hypothetical=True,
            )],
            registry=load_seller_scenario_registry(SC),
        )
    if changed:
        prior_findings=[
            GovernedStrategyFinding(
                finding_id=f"P-{i}",subject_property_id="SUBJECT-1",dimension=d,state=s,
                summary=f"Prior {d}",baseline_certified=True,qa_status="PASS",output_tier="SELLER",
                freshness_state="CURRENT",evidence_fingerprint=f"{300+i:064x}",
            )
            for i,(d,s) in enumerate([
                ("BUYER_DEPTH","DEEP"),("VERIFIED_DIFFERENTIATION","STRONG"),
                ("NEW_CONSTRUCTION_PRESSURE","LOW"),("PRICING_RESPONSE_ENVIRONMENT","RESPONSIVE"),
                ("WEEK_OVER_WEEK_DIRECTION","STABLE"),
            ],1)
        ]
        prior_opp=build_seller_opportunity(
            subject_property_id="SUBJECT-1",alternatives=[],
            registry=load_seller_opportunity_registry(O),
        )
        prior_strategy=build_property_seller_strategy(
            opportunity=prior_opp,m11_001_certified=True,m11_001_evidence_fingerprint=FP1,
            findings=prior_findings,registry=load_seller_strategy_registry(S),
        )
        snaps=[
            GovernedTimelineSnapshot("S-1","2026-09-01T09:00:00-07:00",prior_strategy,True,"1"*64),
            GovernedTimelineSnapshot(
                "S-2","2026-09-08T09:00:00-07:00",strategy,True,"2"*64,
                scenario,with_scenario,FP3 if with_scenario else None,
            ),
        ]
    else:
        snaps=[GovernedTimelineSnapshot(
            "S-1","2026-09-08T09:00:00-07:00",strategy,True,"2"*64,
            scenario,with_scenario,FP3 if with_scenario else None,
        )]
    timeline=build_seller_decision_timeline(snapshots=snaps,registry=load_seller_timeline_registry(T))
    return opp,strategy,scenario,timeline


def reg():
    return load_communication_registry(C)


def translate(audience="SELLER", **kwargs):
    opp,strategy,scenario,timeline=build_inputs(**kwargs)
    return translate_seller_intelligence(
        audience=audience,opportunity=opp,strategy=strategy,scenario=scenario,timeline=timeline,
        m11_001_certified=True,m11_002_certified=True,m11_003_certified=scenario is not None,m11_004_certified=True,
        m11_001_evidence_fingerprint=FP1,m11_002_evidence_fingerprint=FP2,
        m11_003_evidence_fingerprint=FP3 if scenario is not None else None,
        m11_004_evidence_fingerprint=FP4,registry=reg(),
    )


@pytest.mark.parametrize("audience",["INTERNAL","AGENT","SELLER"])
def test_authorized_audiences_render_deterministically(audience):
    a=translate(audience)
    b=translate(audience)
    assert a.projection_fingerprint==b.projection_fingerprint
    assert a.output_tier==audience
    assert a.public_eligible is False
    assert a.external_action_capability=="NONE"


def test_public_audience_is_rejected():
    with pytest.raises(ValueError,match="public seller-strategy communication prohibited"):
        translate("PUBLIC")


def test_facts_and_hypotheticals_are_distinct_statement_types():
    p=translate()
    kinds={s.statement_type for s in p.statements}
    assert "FACT" in kinds
    assert "HYPOTHETICAL" in kinds
    assert "MONITORING_GUIDANCE" in kinds


def test_hypothetical_language_remains_explicit():
    p=translate()
    h=[s for s in p.statements if s.statement_type=="HYPOTHETICAL"]
    assert h
    assert all(s.text.startswith("Hypothetical only:") for s in h)
    assert any("not a statement of current fact" in q for q in p.qualifiers)


def test_competitive_pressure_qualifier_is_preserved():
    p=translate()
    assert any("not a valuation" in q for q in p.qualifiers)
    assert any("list-price recommendation" in q for q in p.qualifiers)


def test_missing_or_suppressed_limitations_are_preserved():
    p=translate(missing_week=True)
    assert "WEEK_OVER_WEEK_DIRECTION:MISSING" in p.limitations
    limitation_statements=[s.text for s in p.statements if s.statement_type=="LIMITATION"]
    assert any("WEEK_OVER_WEEK_DIRECTION:MISSING" in x for x in limitation_statements)


def test_monitoring_guidance_is_non_prescriptive():
    p=translate()
    m=[s for s in p.statements if s.statement_type=="MONITORING_GUIDANCE"]
    assert m
    assert "No automatic action is authorized." in m[0].text
    assert any("does not authorize a price change" in q for q in p.qualifiers)


def test_no_scenario_does_not_emit_hypothetical_statements_or_qualifier():
    p=translate(with_scenario=False)
    assert not [s for s in p.statements if s.statement_type=="HYPOTHETICAL"]
    assert not any("Hypothetical scenario content" in q for q in p.qualifiers)


def test_no_monitoring_change_emits_no_monitoring_statement():
    p=translate(changed=False)
    assert not [s for s in p.statements if s.statement_type=="MONITORING_GUIDANCE"]


def test_every_statement_has_lineage():
    p=translate()
    assert all(s.lineage_fingerprints for s in p.statements)


def test_uncertified_required_parent_fails_closed():
    opp,strategy,scenario,timeline=build_inputs()
    with pytest.raises(ValueError,match="certified M11-001, M11-002, and M11-004 inputs required"):
        translate_seller_intelligence(
            audience="SELLER",opportunity=opp,strategy=strategy,scenario=scenario,timeline=timeline,
            m11_001_certified=False,m11_002_certified=True,m11_003_certified=True,m11_004_certified=True,
            m11_001_evidence_fingerprint=FP1,m11_002_evidence_fingerprint=FP2,
            m11_003_evidence_fingerprint=FP3,m11_004_evidence_fingerprint=FP4,registry=reg(),
        )


def test_scenario_requires_certification_metadata():
    opp,strategy,scenario,timeline=build_inputs()
    with pytest.raises(ValueError,match="certified M11-003 scenario context required"):
        translate_seller_intelligence(
            audience="SELLER",opportunity=opp,strategy=strategy,scenario=scenario,timeline=timeline,
            m11_001_certified=True,m11_002_certified=True,m11_003_certified=False,m11_004_certified=True,
            m11_001_evidence_fingerprint=FP1,m11_002_evidence_fingerprint=FP2,
            m11_003_evidence_fingerprint=None,m11_004_evidence_fingerprint=FP4,registry=reg(),
        )


def test_prohibited_price_value_outcome_and_action_fields_do_not_exist():
    names={x.name for x in fields(type(translate()))}
    assert names.isdisjoint(set(reg()["prohibited_output_fields"]))
