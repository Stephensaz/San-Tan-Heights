from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import re

_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class PresentationAudience(str, Enum):
    AGENT = "AGENT"
    SELLER = "SELLER"
    PUBLIC = "PUBLIC"


class PresentationChannel(str, Enum):
    WEB = "WEB"
    PDF = "PDF"
    PRINT = "PRINT"


@dataclass(frozen=True)
class PresentationPackageInput:
    """Immutable handoff from governed report production into presentation.

    This descriptor contains references and fingerprints only. It cannot create,
    infer, score, reword, or reinterpret property intelligence.
    """

    source_report_id: str
    source_report_version: int
    audience: PresentationAudience
    channel: PresentationChannel
    canonical_payload_hash: str
    presentation_input_hash: str
    render_contract_version: str
    template_id: str
    template_version: str
    presentation_contract_id: str = "STH-PRESENTATION-CONSUMER-SYSTEM"
    presentation_contract_version: str = "1.0.0"

    def __post_init__(self) -> None:
        if not self.source_report_id.strip():
            raise ValueError("source_report_id is required")
        if self.source_report_version < 1:
            raise ValueError("source_report_version must be positive")
        if not _SHA256.fullmatch(self.canonical_payload_hash):
            raise ValueError("canonical_payload_hash must be lowercase sha256")
        if not _SHA256.fullmatch(self.presentation_input_hash):
            raise ValueError("presentation_input_hash must be lowercase sha256")
        for name, value in (
            ("render_contract_version", self.render_contract_version),
            ("template_id", self.template_id),
            ("template_version", self.template_version),
        ):
            if not value.strip():
                raise ValueError(f"{name} is required")
        if self.presentation_contract_id != "STH-PRESENTATION-CONSUMER-SYSTEM":
            raise ValueError("unexpected presentation contract id")
        if self.presentation_contract_version != "1.0.0":
            raise ValueError("unexpected presentation contract version")

    @property
    def target_key(self) -> str:
        return ":".join(
            (
                self.source_report_id,
                str(self.source_report_version),
                self.audience.value,
                self.channel.value,
                self.template_id,
                self.template_version,
            )
        )
