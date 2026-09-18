from copy import deepcopy

import pytest

from src.seller_intelligence.opportunity import (
    GovernedAlternativeInput,
    build_seller_opportunity,
    load_seller_opportunity_registry,
)

REGISTRY="registries/seller_intelligence/m11-001-seller-opportunity-v1.0.yaml"


def registry():
    return load_seller_opportunity_registry(REGISTRY)


def alt(i, kind, *, freshness="CURRENT", tier="SELLER", qa="PASS", certified=True):
    return GovernedAlternativeInput(
        alternative_id=f"A-{i}",
        subject_property_id="SUBJECT-1",
        alternative_property_id=f"P-{i}",
        alternative_type=kind,
        baseline_certified=certified,
        qa_status=qa,
        output_tier=tier,
        freshness_state=freshness,
        evidence_fingerprint=f"{i:064x}"[-64:],
    )


def test_current_buyer_alternative_set_is_deterministic():
    rows=[
        alt(1,"CLOSE_SUBSTITUTE"),
        alt(2,"STRICT_SUBSTITUTE"),
        alt(3,"BUILDER_ALTERNATIVE"),
    ]
    a=build_seller_opportunity(subject_property_id="SUBJECT-1",alternatives=rows,registry=registry())
    b=build_seller_opportunity(subject_property_id="SUBJECT-1",alternatives=reversed(rows),registry=registry())
    assert a.result_fingerprint==b.result_fingerprint
    assert a.alternative_set.alternative_set_fingerprint==b.alternative_set.alternative_set_fingerprint


def test_stale_non_seller_and_qa_failed_inputs_are_suppressed():
    rows=[
        alt(1,"CLOSE_SUBSTITUTE"),
        alt(2,"CLOSE_SUBSTITUTE",freshness="STALE"),
        alt(3,"STRICT_SUBSTITUTE",tier="AGENT"),
        alt(4,"BUILDER_ALTERNATIVE",qa="FAIL"),
    ]
    result=build_seller_opportunity(subject_property_id="SUBJECT-1",alternatives=rows,registry=registry())
    assert result.alternative_set.close_substitute_ids==("P-1",)
    assert result.alternative_set.strict_substitute_ids==()
    assert result.alternative_set.builder_alternative_ids==()
    assert result.alternative_set.suppressed_input_ids==("A-2","A-3","A-4")


def test_uncertified_baseline_input_fails_closed():
    with pytest.raises(ValueError,match="uncertified community baseline input prohibited"):
        build_seller_opportunity(
            subject_property_id="SUBJECT-1",
            alternatives=[alt(1,"CLOSE_SUBSTITUTE",certified=False)],
            registry=registry(),
        )


def test_high_competitive_pressure_requires_available_and_builder_thresholds():
    rows=[
        alt(1,"CLOSE_SUBSTITUTE"),alt(2,"CLOSE_SUBSTITUTE"),alt(3,"CLOSE_SUBSTITUTE"),
        alt(4,"STRICT_SUBSTITUTE"),alt(5,"STRICT_SUBSTITUTE"),
        alt(6,"BUILDER_ALTERNATIVE"),alt(7,"BUILDER_ALTERNATIVE"),
    ]
    result=build_seller_opportunity(subject_property_id="SUBJECT-1",alternatives=rows,registry=registry())
    assert result.competitive_pressure.level=="HIGH"
    assert result.competitive_pressure.available_alternative_count==5
    assert result.competitive_pressure.builder_alternative_count==2


def test_moderate_pressure():
    rows=[alt(1,"CLOSE_SUBSTITUTE"),alt(2,"STRICT_SUBSTITUTE"),alt(3,"BUILDER_ALTERNATIVE")]
    result=build_seller_opportunity(subject_property_id="SUBJECT-1",alternatives=rows,registry=registry())
    assert result.competitive_pressure.level=="MODERATE"


def test_low_pressure():
    result=build_seller_opportunity(subject_property_id="SUBJECT-1",alternatives=[],registry=registry())
    assert result.competitive_pressure.level=="LOW"


def test_output_is_seller_only_nonpublic_and_has_no_action_capability():
    result=build_seller_opportunity(subject_property_id="SUBJECT-1",alternatives=[],registry=registry())
    assert result.output_tier=="SELLER"
    assert result.public_eligible is False
    assert result.external_action_capability=="NONE"


def test_pressure_qualifier_explicitly_disclaims_valuation_and_prediction():
    result=build_seller_opportunity(subject_property_id="SUBJECT-1",alternatives=[],registry=registry())
    q=result.competitive_pressure.qualifier.lower()
    assert "not a valuation" in q
    assert "list-price recommendation" in q
    assert "sale-price prediction" in q
    assert "outcome guarantee" in q


def test_duplicate_input_id_rejected():
    rows=[alt(1,"CLOSE_SUBSTITUTE"),alt(1,"STRICT_SUBSTITUTE")]
    with pytest.raises(ValueError,match="duplicate alternative_id"):
        build_seller_opportunity(subject_property_id="SUBJECT-1",alternatives=rows,registry=registry())


def test_subject_mismatch_rejected():
    row=alt(1,"CLOSE_SUBSTITUTE")
    row=type(row)(**{**row.__dict__,"subject_property_id":"OTHER"})
    with pytest.raises(ValueError,match="subject_property_id mismatch"):
        build_seller_opportunity(subject_property_id="SUBJECT-1",alternatives=[row],registry=registry())
