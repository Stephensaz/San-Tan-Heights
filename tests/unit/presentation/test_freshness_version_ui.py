import pytest

from src.presentation.freshness import (
    FreshnessState,
    FreshnessVersionUi,
    GovernedFreshnessVersionDTO,
    ReportDesignation,
    SectionFreshnessDTO,
)
from src.presentation.package import PresentationAudience


def dto(
    *,
    audience=PresentationAudience.PUBLIC,
    designation=ReportDesignation.CURRENT,
    freshness_state=FreshnessState.CURRENT,
    generated_at="2026-09-17T22:00:00Z",
    effective_as_of="2026-09-17T20:00:00Z",
    property_verified_through="2026-09-16",
    market_data_through="2026-09-15",
    builder_data_checked="2026-09-14",
    report_version=7,
):
    return GovernedFreshnessVersionDTO(
        property_id="property-1",
        audience=audience,
        report_version=report_version,
        designation=designation,
        freshness_state=freshness_state,
        generated_at=generated_at,
        effective_as_of=effective_as_of,
        property_verified_through=property_verified_through,
        market_data_through=market_data_through,
        builder_data_checked=builder_data_checked,
        current_report_path="/properties/property-1",
        sections=(
            SectionFreshnessDTO("property-identity", "Property information", FreshnessState.CURRENT, "2026-09-16"),
            SectionFreshnessDTO("market-context", "Market information", FreshnessState.AGING, "2026-09-15"),
            SectionFreshnessDTO("evidence", "Evidence", FreshnessState.STALE, "2026-09-10"),
        ),
    )


def test_public_surface_is_minimal_and_uses_governed_data_dates():
    panel = FreshnessVersionUi().build(dto())
    assert panel.report_badge == "Current report"
    assert panel.version_label is None
    assert panel.generated_date is None
    assert panel.sections == ()
    assert tuple(item.label for item in panel.dates) == (
        "Property information verified through",
        "Market information through",
        "Builder information checked",
    )


def test_seller_surface_shows_key_dates_and_section_freshness_without_generated_date():
    panel = FreshnessVersionUi().build(dto(audience=PresentationAudience.SELLER))
    assert panel.version_label == "Report version 7"
    assert panel.generated_date is None
    assert tuple(item.label for item in panel.dates) == (
        "Property information verified through",
        "Market information through",
        "Builder information checked",
        "Effective as of",
    )
    assert tuple(section.section_id for section in panel.sections) == (
        "property-identity",
        "market-context",
        "evidence",
    )


def test_agent_surface_has_rich_version_and_generated_context():
    panel = FreshnessVersionUi().build(dto(audience=PresentationAudience.AGENT))
    assert panel.version_label == "Report version 7"
    assert panel.generated_date.label == "Report generated"
    assert panel.generated_date.value == "2026-09-17T22:00:00Z"
    assert panel.dates[0].label == "Effective as of"
    assert len(panel.sections) == 3


def test_generated_date_is_never_substituted_for_data_freshness():
    panel = FreshnessVersionUi().build(
        dto(
            audience=PresentationAudience.AGENT,
            generated_at="2099-01-01T00:00:00Z",
            property_verified_through="2026-09-16",
        )
    )
    property_date = next(item for item in panel.dates if item.key == "property_verified_through")
    assert property_date.value == "2026-09-16"
    assert property_date.value != panel.generated_date.value


def test_historical_report_banner_is_permanent_even_when_data_state_is_current():
    panel = FreshnessVersionUi().build(
        dto(
            designation=ReportDesignation.HISTORICAL,
            freshness_state=FreshnessState.CURRENT,
        )
    )
    assert panel.report_badge == "Historical report"
    assert panel.historical_banner is not None
    assert panel.current_report_path == "/properties/property-1"


def test_stale_state_has_explicit_warning_without_falsehood_claim():
    panel = FreshnessVersionUi().build(dto(freshness_state=FreshnessState.STALE))
    assert panel.overall_state_label == "Stale"
    assert "stale" in panel.stale_warning.lower()
    assert "false" not in panel.stale_warning.lower()


def test_unknown_and_not_applicable_states_do_not_require_dates():
    unknown = GovernedFreshnessVersionDTO(
        property_id="property-1",
        audience=PresentationAudience.PUBLIC,
        report_version=1,
        designation=ReportDesignation.CURRENT,
        freshness_state=FreshnessState.UNKNOWN,
        generated_at=None,
        effective_as_of=None,
        property_verified_through=None,
        market_data_through=None,
        builder_data_checked=None,
        current_report_path="/properties/property-1",
    )
    panel = FreshnessVersionUi().build(unknown)
    assert panel.overall_state_label == "Freshness unknown"
    assert panel.dates == ()


def test_known_freshness_state_requires_governed_data_date_not_render_time():
    with pytest.raises(ValueError, match="governed freshness date"):
        GovernedFreshnessVersionDTO(
            property_id="property-1",
            audience=PresentationAudience.PUBLIC,
            report_version=1,
            designation=ReportDesignation.CURRENT,
            freshness_state=FreshnessState.CURRENT,
            generated_at="2026-09-17T22:00:00Z",
            effective_as_of=None,
            property_verified_through=None,
            market_data_through=None,
            builder_data_checked=None,
            current_report_path="/properties/property-1",
        )


def test_ui_uses_no_generic_updated_claim():
    panel = FreshnessVersionUi().build(dto(audience=PresentationAudience.AGENT))
    payload = str(panel.canonical_payload()).lower()
    assert "updated" not in payload


def test_fingerprint_is_deterministic():
    first = FreshnessVersionUi().build(dto(audience=PresentationAudience.AGENT))
    second = FreshnessVersionUi().build(dto(audience=PresentationAudience.AGENT))
    assert first.fingerprint == second.fingerprint
    assert len(first.fingerprint) == 64
