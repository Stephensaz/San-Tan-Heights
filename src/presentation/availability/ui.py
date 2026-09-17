from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from hashlib import sha256

from src.presentation.package import PresentationAudience
from src.shared.canonical_json import canonical_json


class AvailabilityState(str, Enum):
    EMPTY = "EMPTY"
    MISSING = "MISSING"
    UNAVAILABLE = "UNAVAILABLE"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    WITHHELD = "WITHHELD"


_STATE_COPY = {
    AvailabilityState.EMPTY: (
        "No information to display",
        "There is no governed information to display for this section.",
    ),
    AvailabilityState.MISSING: (
        "Information not yet verified",
        "This information is not currently available as a verified report fact.",
    ),
    AvailabilityState.UNAVAILABLE: (
        "Information unavailable",
        "This information is currently unavailable from the governed source.",
    ),
    AvailabilityState.NOT_APPLICABLE: (
        "Not applicable",
        "This section does not apply to this property or report.",
    ),
    AvailabilityState.WITHHELD: (
        "Information not shown",
        "This information is not available in this report view.",
    ),
}


@dataclass(frozen=True)
class GovernedAvailabilityDTO:
    property_id: str
    audience: PresentationAudience
    section_id: str
    state: AvailabilityState
    source_status: str | None = None
    diagnostic_code: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.property_id, str) or not self.property_id.strip():
            raise ValueError("property_id is required")
        if not isinstance(self.audience, PresentationAudience):
            raise ValueError("audience must be a PresentationAudience")
        if not isinstance(self.section_id, str) or not self.section_id.strip():
            raise ValueError("section_id is required")
        if not isinstance(self.state, AvailabilityState):
            raise ValueError("state must be an AvailabilityState")


@dataclass(frozen=True)
class AvailabilityStateView:
    property_id: str
    audience: PresentationAudience
    section_id: str
    state: AvailabilityState
    title: str
    message: str
    source_status: str | None
    diagnostic_code: str | None

    def canonical_payload(self) -> dict[str, object]:
        return {
            "property_id": self.property_id,
            "audience": self.audience.value,
            "section_id": self.section_id,
            "state": self.state.value,
            "title": self.title,
            "message": self.message,
            "source_status": self.source_status,
            "diagnostic_code": self.diagnostic_code,
        }

    @property
    def fingerprint(self) -> str:
        return sha256(canonical_json(self.canonical_payload()).encode("utf-8")).hexdigest()


class AvailabilityStateUi:
    """Render governed absence states without inferring property facts or causes."""

    def build(self, dto: GovernedAvailabilityDTO) -> AvailabilityStateView:
        if not isinstance(dto, GovernedAvailabilityDTO):
            raise ValueError("AvailabilityStateUi requires a GovernedAvailabilityDTO")

        title, message = _STATE_COPY[dto.state]

        if dto.audience is PresentationAudience.AGENT:
            source_status = dto.source_status
            diagnostic_code = dto.diagnostic_code
        else:
            source_status = None
            diagnostic_code = None

        return AvailabilityStateView(
            property_id=dto.property_id,
            audience=dto.audience,
            section_id=dto.section_id,
            state=dto.state,
            title=title,
            message=message,
            source_status=source_status,
            diagnostic_code=diagnostic_code,
        )
