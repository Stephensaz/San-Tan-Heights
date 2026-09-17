from __future__ import annotations
from dataclasses import dataclass
from typing import Any

from src.report_builder.schema import CanonicalReportSchema
from src.shared.canonical_json import canonical_json
from src.shared.hash import sha256_text


class CanonicalPayloadHashError(ValueError):
    pass


@dataclass(frozen=True)
class CanonicalPayloadIdentity:
    canonical_payload_hash: str
    canonical_json_text: str


class CanonicalPayloadHashEngine:
    """Hashes the exact canonical report payload after schema/cross-reference validation."""

    def __init__(self, schema: CanonicalReportSchema):
        self.schema = schema

    def calculate(self, payload: dict[str, Any]) -> CanonicalPayloadIdentity:
        if not isinstance(payload, dict):
            raise CanonicalPayloadHashError("canonical payload must be an object")
        self.schema.validate(payload)
        text = canonical_json(payload)
        return CanonicalPayloadIdentity(sha256_text(text), text)

    def verify(self, payload: dict[str, Any], expected_hash: str) -> CanonicalPayloadIdentity:
        if len(expected_hash) != 64 or any(c not in '0123456789abcdef' for c in expected_hash):
            raise CanonicalPayloadHashError("expected_hash must be a lowercase SHA-256 hex digest")
        identity = self.calculate(payload)
        if identity.canonical_payload_hash != expected_hash:
            raise CanonicalPayloadHashError("CANONICAL_PAYLOAD_HASH_MISMATCH")
        return identity
