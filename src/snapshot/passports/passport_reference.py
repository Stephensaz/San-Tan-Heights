from __future__ import annotations
from dataclasses import dataclass
import re

_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_QA = {"PASS", "REVIEW_REQUIRED", "FAIL", "PENDING"}


@dataclass(frozen=True)
class PassportReference:
    passport_id: str
    passport_version: str
    passport_semantic_fingerprint: str
    passport_qa_status: str
    finding_id: str
    evidence_reference_set_hash: str

    def validate(self) -> None:
        for field_name in ("passport_id", "passport_version", "finding_id"):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{field_name} is required")
        for field_name in ("passport_semantic_fingerprint", "evidence_reference_set_hash"):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not _HEX64.fullmatch(value):
                raise ValueError(f"{field_name} must be lowercase sha256")
        if self.passport_qa_status not in _QA:
            raise ValueError("unknown passport_qa_status")
