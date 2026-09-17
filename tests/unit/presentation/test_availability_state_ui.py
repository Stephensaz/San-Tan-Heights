import pytest

from src.presentation.availability import (
    AvailabilityState,
    AvailabilityStateUi,
    GovernedAvailabilityDTO,
)
from src.presentation.package import PresentationAudience


def dto(
    *,
    audience=PresentationAudience.PUBLIC,
    state=AvailabilityState.EMPTY,
    source_status="SOURCE_NOT_RETURNED",
    diagnostic_code="NO_ROWS",
):
    return GovernedAvailabilityDTO(
        property_id="property-1",
        audience=audience,
        section_id="evidence",
        state=state,
        source_status=source_status,
        diagnostic_code=diagnostic_code,
    )


def test_empty_state_does_not_claim_property_feature_absence():
    view = AvailabilityStateUi().build(dto(state=AvailabilityState.EMPTY))
    assert view.title == "No information to display"
    assert "no governed information" in view.message.lower()
    assert "does not have" not in view.message.lower()
    assert "no feature" not in view.message.lower()


def test_missing_state_is_not_converted_into_negative_fact():
    view = AvailabilityStateUi().build(dto(state=AvailabilityState.MISSING))
    assert view.title == "Information not yet verified"
    assert "not currently available as a verified report fact" in view.message
    assert "absent" not in view.message.lower()


def test_unavailable_state_preserves_source_unavailability_without_guessing_reason():
    view = AvailabilityStateUi().build(dto(state=AvailabilityState.UNAVAILABLE))
    assert view.title == "Information unavailable"
    assert "governed source" in view.message
    assert "because" not in view.message.lower()


def test_not_applicable_is_distinct_from_missing_and_unavailable():
    view = AvailabilityStateUi().build(dto(state=AvailabilityState.NOT_APPLICABLE))
    assert view.title == "Not applicable"
    assert view.state is AvailabilityState.NOT_APPLICABLE


def test_withheld_state_does_not_reveal_private_reason():
    view = AvailabilityStateUi().build(
        dto(
            audience=PresentationAudience.PUBLIC,
            state=AvailabilityState.WITHHELD,
            source_status="AGENT_ONLY",
            diagnostic_code="PRIVATE_CLASSIFICATION",
        )
    )
    assert view.title == "Information not shown"
    assert view.source_status is None
    assert view.diagnostic_code is None
    assert "private" not in view.message.lower()
    assert "agent" not in view.message.lower()


def test_seller_and_public_do_not_receive_diagnostics():
    for audience in (PresentationAudience.SELLER, PresentationAudience.PUBLIC):
        view = AvailabilityStateUi().build(dto(audience=audience))
        assert view.source_status is None
        assert view.diagnostic_code is None


def test_agent_may_receive_governed_diagnostics():
    view = AvailabilityStateUi().build(dto(audience=PresentationAudience.AGENT))
    assert view.source_status == "SOURCE_NOT_RETURNED"
    assert view.diagnostic_code == "NO_ROWS"


def test_ui_rejects_untyped_input():
    with pytest.raises(ValueError, match="GovernedAvailabilityDTO"):
        AvailabilityStateUi().build(object())


def test_required_identity_fields_fail_closed():
    with pytest.raises(ValueError, match="property_id"):
        GovernedAvailabilityDTO(
            property_id="",
            audience=PresentationAudience.PUBLIC,
            section_id="evidence",
            state=AvailabilityState.EMPTY,
        )
    with pytest.raises(ValueError, match="section_id"):
        GovernedAvailabilityDTO(
            property_id="property-1",
            audience=PresentationAudience.PUBLIC,
            section_id="",
            state=AvailabilityState.EMPTY,
        )


def test_output_is_deterministic():
    first = AvailabilityStateUi().build(dto(audience=PresentationAudience.AGENT))
    second = AvailabilityStateUi().build(dto(audience=PresentationAudience.AGENT))
    assert first.fingerprint == second.fingerprint
    assert len(first.fingerprint) == 64
