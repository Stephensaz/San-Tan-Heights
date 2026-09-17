from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Mapping
from uuid import UUID
import re

_SHA256 = re.compile(r'^[0-9a-f]{64}$')
_RUN_STATES = frozenset({'CREATED','IN_PROGRESS','BLOCKED','PASSED','FAILED','REVOKED'})
_VERDICTS = frozenset({'GO','NO_GO'})
_CHECK_STATUSES = frozenset({'PASS','FAIL','BLOCKED','NOT_RUN'})


def _require_hash(value: str, field_name: str) -> None:
    if not _SHA256.fullmatch(value):
        raise ValueError(f'{field_name} must be a lowercase SHA-256 hex digest')


@dataclass(frozen=True)
class ProductionCertificationRun:
    production_certification_id: UUID
    system_certification_run_id: UUID
    contract_version: str
    candidate_version: str
    candidate_fingerprint: str
    created_by: str
    correlation_id: UUID | None = None
    run_state: str = 'CREATED'
    verdict: str | None = None

    def __post_init__(self) -> None:
        _require_hash(self.candidate_fingerprint, 'candidate_fingerprint')
        if self.run_state not in _RUN_STATES:
            raise ValueError('unknown production certification run_state')
        if self.verdict is not None and self.verdict not in _VERDICTS:
            raise ValueError('unknown production certification verdict')
        for name in ('contract_version','candidate_version','created_by'):
            if not getattr(self, name).strip():
                raise ValueError(f'{name} is required')


@dataclass(frozen=True)
class ProductionEvidence:
    production_evidence_id: UUID
    production_certification_id: UUID
    evidence_type: str
    subject_key: str
    evidence_hash: str
    captured_by: str
    evidence_payload: Mapping[str, Any] = field(default_factory=dict)
    source_uri: str | None = None

    def __post_init__(self) -> None:
        _require_hash(self.evidence_hash, 'evidence_hash')
        if not self.evidence_type.strip() or not self.subject_key.strip() or not self.captured_by.strip():
            raise ValueError('evidence_type, subject_key, and captured_by are required')


@dataclass(frozen=True)
class ProductionCheckResult:
    production_check_result_id: UUID
    production_certification_id: UUID
    stage_code: str
    check_code: str
    status: str
    evidence_hash: str
    observed_by: str
    detail: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_hash(self.evidence_hash, 'evidence_hash')
        if self.status not in _CHECK_STATUSES:
            raise ValueError('unknown production certification check status')
        if not self.stage_code.strip() or not self.check_code.strip() or not self.observed_by.strip():
            raise ValueError('stage_code, check_code, and observed_by are required')
