from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from hashlib import sha256
from typing import Iterable

from src.presentation.package import PresentationAudience
from src.shared.canonical_json import canonical_json


class FreshnessState(str, Enum):
    CURRENT = "CURRENT"
    AGING = "AGING"
    STALE = "STALE"
    HISTORICAL = "HISTORICAL"
    UNKNOWN = "UNKNOWN"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class ReportDesignation(str, Enum):
    CURRENT = "CURRENT"
    HISTORICAL = "HISTORICAL"


_STATE_LABELS = {
    FreshnessState.CURRENT: "Current",
    FreshnessState.AGING: "Aging",
    FreshnessState.STALE: "Stale",
    FreshnessState.HISTORICAL: "Historical",
    FreshnessState.UNKNOWN: "Freshness unknown",
    FreshnessState.NOT_APPLICABLE: "Not applicable",
}


@dataclass(frozen=True)
class SectionFreshnessDTO:
    section_id: str
    label: str
    state: FreshnessState
    as_of: str | None

    def __post_init__(self) -> None:
        if not self.section_id.strip():
            raise ValueError("section_id is required")
        if not self.label.strip():
            raise ValueError("section freshness label is required")
        if not isinstance(self.state, FreshnessState):
            raise ValueError("section freshness state must be a FreshnessState")


@dataclass(frozen=True)
class GovernedFreshnessVersionDTO:
    property_id: str
    audience: PresentationAudience
    report_version: int
    designation: ReportDesignation
    freshness_state: FreshnessState
    generated_at: str | None
    effective_as_of: str | None
    property_verified_through: str | None
    market_data_through: str | None
    builder_data_checked: str | None
    current_report_path: str
    sections: tuple[SectionFreshnessDTO, ...] = ()

    def __post_init__(self) -> None:
        if not self.property_id.strip():
            raise ValueError("property_id is required")
        if not isinstance(self.audience, PresentationAudience):
            raise ValueError("audience must be a PresentationAudience")
        if self.report_version < 1:
            raise ValueError("report_version must be positive")
        if not isinstance(self.designation, ReportDesignation):
            raise ValueError("designation must be a ReportDesignation")
        if not isinstance(self.freshness_state, FreshnessState):
            raise ValueError("freshness_state must be a FreshnessState")
        if not self.current_report_path.strip():
            raise ValueError("current_report_path is required")
        if self.freshness_state not in {FreshnessState.UNKNOWN, FreshnessState.NOT_APPLICABLE}:
            if not any(
                (
                    self.property_verified_through,
                    self.market_data_through,
                    self.builder_data_checked,
                    self.effective_as_of,
                )
            ):
                raise ValueError("governed freshness date is required for a known freshness state")


@dataclass(frozen=True)
class FreshnessDateLabel:
    key: str
    label: str
    value: str

    def canonical_payload(self) -> dict[str, str]:
        return {"key": self.key, "label": self.label, "value": self.value}


@dataclass(frozen=True)
class SectionFreshnessView:
    section_id: str
    label: str
    state: FreshnessState
    state_label: str
    as_of: str | None

    def canonical_payload(self) -> dict[str, object]:
        return {
            "section_id": self.section_id,
            "label": self.label,
            "state": self.state.value,
            "state_label": self.state_label,
            "as_of": self.as_of,
        }


@dataclass(frozen=True)
class FreshnessVersionPanel:
    audience: PresentationAudience
    property_id: str
    designation: ReportDesignation
    report_badge: str
    overall_state: FreshnessState
    overall_state_label: str
    stale_warning: str | None
    historical_banner: str | None
    dates: tuple[FreshnessDateLabel, ...]
    version_label: str | None
    generated_date: FreshnessDateLabel | None
    current_report_path: str
    sections: tuple[SectionFreshnessView, ...]

    def canonical_payload(self) -> dict[str, object]:
        return {
            "audience": self.audience.value,
            "property_id": self.property_id,
            "designation": self.designation.value,
            "report_badge": self.report_badge,
            "overall_state": self.overall_state.value,
            "overall_state_label": self.overall_state_label,
            "stale_warning": self.stale_warning,
            "historical_banner": self.historical_banner,
            "dates": [item.canonical_payload() for item in self.dates],
            "version_label": self.version_label,
            "generated_date": None if self.generated_date is None else self.generated_date.canonical_payload(),
            "current_report_path": self.current_report_path,
            "sections": [section.canonical_payload() for section in self.sections],
        }

    @property
    def fingerprint(self) -> str:
        return sha256(canonical_json(self.canonical_payload()).encode("utf-8")).hexdigest()


class FreshnessVersionUi:
    """Present governed freshness/version metadata without deriving recency from timestamps."""

    def build(self, dto: GovernedFreshnessVersionDTO) -> FreshnessVersionPanel:
        if not isinstance(dto, GovernedFreshnessVersionDTO):
            raise ValueError("FreshnessVersionUi requires a GovernedFreshnessVersionDTO")

        dates: list[FreshnessDateLabel] = []

        def add(key: str, label: str, value: str | None) -> None:
            if value is not None:
                dates.append(FreshnessDateLabel(key=key, label=label, value=value))

        if dto.audience is PresentationAudience.AGENT:
            add("effective_as_of", "Effective as of", dto.effective_as_of)
            add("property_verified_through", "Property information verified through", dto.property_verified_through)
            add("market_data_through", "Market information through", dto.market_data_through)
            add("builder_data_checked", "Builder information checked", dto.builder_data_checked)
            version_label = f"Report version {dto.report_version}"
            generated_date = (
                None
                if dto.generated_at is None
                else FreshnessDateLabel("generated_at", "Report generated", dto.generated_at)
            )
            sections = self._sections(dto.sections)
        elif dto.audience is PresentationAudience.SELLER:
            add("property_verified_through", "Property information verified through", dto.property_verified_through)
            add("market_data_through", "Market information through", dto.market_data_through)
            add("builder_data_checked", "Builder information checked", dto.builder_data_checked)
            add("effective_as_of", "Effective as of", dto.effective_as_of)
            version_label = f"Report version {dto.report_version}"
            generated_date = None
            sections = tuple(
                section
                for section in self._sections(dto.sections)
                if section.state is not FreshnessState.NOT_APPLICABLE
            )
        else:
            add("property_verified_through", "Property information verified through", dto.property_verified_through)
            add("market_data_through", "Market information through", dto.market_data_through)
            add("builder_data_checked", "Builder information checked", dto.builder_data_checked)
            version_label = None
            generated_date = None
            sections = ()

        historical_banner = (
            "Historical report — view the current report for the latest governed information."
            if dto.designation is ReportDesignation.HISTORICAL
            else None
        )
        report_badge = "Historical report" if dto.designation is ReportDesignation.HISTORICAL else "Current report"
        stale_warning = (
            "Some governed information is stale. Review the dates shown before relying on this report."
            if dto.freshness_state is FreshnessState.STALE
            else None
        )

        return FreshnessVersionPanel(
            audience=dto.audience,
            property_id=dto.property_id,
            designation=dto.designation,
            report_badge=report_badge,
            overall_state=dto.freshness_state,
            overall_state_label=_STATE_LABELS[dto.freshness_state],
            stale_warning=stale_warning,
            historical_banner=historical_banner,
            dates=tuple(dates),
            version_label=version_label,
            generated_date=generated_date,
            current_report_path=dto.current_report_path,
            sections=sections,
        )

    @staticmethod
    def _sections(sections: Iterable[SectionFreshnessDTO]) -> tuple[SectionFreshnessView, ...]:
        return tuple(
            SectionFreshnessView(
                section_id=section.section_id,
                label=section.label,
                state=section.state,
                state_label=_STATE_LABELS[section.state],
                as_of=section.as_of,
            )
            for section in sections
        )
