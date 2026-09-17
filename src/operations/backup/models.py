from __future__ import annotations
from dataclasses import dataclass
from uuid import UUID

@dataclass(frozen=True)
class BackupVerificationRequest:
    verification_id: UUID
    backup_id: str
    backup_type: str
    source_environment: str
    expected_sha256: str
    observed_sha256: str
    expected_size_bytes: int
    observed_size_bytes: int
    manifest_fingerprint: str
    verifier_version: str
    verified_by: str

@dataclass(frozen=True)
class BackupVerificationResult:
    status: str  # VERIFIED | FAILED
    reason_codes: tuple[str,...]
