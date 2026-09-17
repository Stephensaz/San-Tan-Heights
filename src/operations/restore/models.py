from __future__ import annotations
from dataclasses import dataclass
from uuid import UUID

@dataclass(frozen=True)
class RestoreVerificationRequest:
    restore_verification_id: UUID
    backup_verification_id: UUID
    restored_environment: str
    schema_version: str
    expected_manifest_fingerprint: str
    observed_manifest_fingerprint: str
    integrity_check_status: str
    row_count_check_status: str
    verifier_version: str
    verified_by: str

@dataclass(frozen=True)
class RestoreVerificationResult:
    status: str  # VERIFIED | FAILED
    reason_codes: tuple[str,...]

@dataclass(frozen=True)
class GlobalPublicationFreeze:
    freeze_id: UUID
    reason_code: str
    restore_verification_id: UUID
    created_by: str
