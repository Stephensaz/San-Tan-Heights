from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from shutil import which
from typing import Mapping, Iterable
import json
from uuid import UUID
import re
import yaml

from src.production_certification.go_live.finalization import FullApproval, CertificationEvidenceBundle
from src.production_certification.go_live.stop_conditions import GoLiveStopResult
from src.shared.canonical_json import canonical_json

_SHA256 = re.compile(r'^[0-9a-f]{64}$')


def _hash(payload: Mapping[str, object]) -> str:
    return sha256(canonical_json(payload).encode('utf-8')).hexdigest()


def _require_hash(value: str, name: str) -> None:
    if not _SHA256.fullmatch(value):
        raise ValueError(f'{name} must be lowercase sha256')


@dataclass(frozen=True)
class FinalCertificationPolicy:
    policy_version: str
    required_rollout_stages: tuple[str, ...]
    required_live_postgresql_checks: tuple[str, ...]
    requires_full_approval: bool
    requires_clear_stop_conditions: bool
    requires_zero_hard_zero_metrics: bool
    blocked_when_live_postgresql_unavailable: bool

    @classmethod
    def load(cls, path: str | Path) -> 'FinalCertificationPolicy':
        data = yaml.safe_load(Path(path).read_text())
        if data.get('status') != 'LOCKED':
            raise ValueError('final certification policy must be LOCKED')
        stages = tuple(str(x) for x in data.get('required_rollout_stages') or ())
        live = tuple(str(x) for x in data.get('required_live_postgresql_checks') or ())
        if not stages or not live:
            raise ValueError('final certification policy requires rollout stages and live PostgreSQL checks')
        return cls(
            str(data['policy_version']), stages, live,
            bool(data.get('requires_full_approval', True)),
            bool(data.get('requires_clear_stop_conditions', True)),
            bool(data.get('requires_zero_hard_zero_metrics', True)),
            bool(data.get('blocked_when_live_postgresql_unavailable', True)),
        )


@dataclass(frozen=True)
class LivePostgresCertificationEvidence:
    available: bool
    executed: bool
    check_statuses: Mapping[str, str]
    evidence_fingerprint: str
    detail: Mapping[str, object]
    candidate_fingerprint: str | None = None
    source_revision: str | None = None

    def __post_init__(self) -> None:
        _require_hash(self.evidence_fingerprint, 'evidence_fingerprint')
        if self.candidate_fingerprint is not None:
            _require_hash(self.candidate_fingerprint, 'candidate_fingerprint')
        if self.source_revision is not None and not self.source_revision.strip():
            raise ValueError('source_revision cannot be blank')


def load_live_postgresql_evidence(path: str | Path) -> LivePostgresCertificationEvidence:
    raw = json.loads(Path(path).read_text())
    supplied = str(raw.get('evidence_fingerprint', ''))
    _require_hash(supplied, 'evidence_fingerprint')
    payload = {k: raw[k] for k in ('schema_version','candidate_fingerprint','source_revision','available','executed','check_statuses','detail') if k in raw}
    expected = _hash(payload)
    if supplied != expected:
        raise ValueError('live PostgreSQL evidence fingerprint mismatch')
    statuses = {str(k): str(v) for k, v in dict(raw.get('check_statuses') or {}).items()}
    return LivePostgresCertificationEvidence(
        bool(raw.get('available')),
        bool(raw.get('executed')),
        statuses,
        supplied,
        dict(raw.get('detail') or {}),
        str(raw['candidate_fingerprint']) if raw.get('candidate_fingerprint') is not None else None,
        str(raw['source_revision']) if raw.get('source_revision') is not None else None,
    )


@dataclass(frozen=True)
class Milestone7FinalCertificationResult:
    production_certification_id: UUID
    candidate_fingerprint: str
    policy_version: str
    status: str
    verdict: str
    reason_codes: tuple[str, ...]
    check_statuses: Mapping[str, str]
    evidence_fingerprint: str


class Milestone7FinalCertificationSuite:
    def evaluate(
        self,
        *,
        policy: FinalCertificationPolicy,
        production_certification_id: UUID,
        candidate_fingerprint: str,
        evidence_bundle: CertificationEvidenceBundle,
        full_approval: FullApproval | None,
        stop_conditions: GoLiveStopResult,
        rollout_stage_certifications: Mapping[str, tuple[str, str]],
        hard_zero_metrics: Mapping[str, int],
        live_postgresql: LivePostgresCertificationEvidence,
    ) -> Milestone7FinalCertificationResult:
        _require_hash(candidate_fingerprint, 'candidate_fingerprint')
        reasons: list[str] = []
        checks: dict[str, str] = {}

        candidate_ok = (
            evidence_bundle.production_certification_id == production_certification_id
            and evidence_bundle.candidate_fingerprint == candidate_fingerprint
            and evidence_bundle.status == 'PASS'
        )
        checks['CERTIFICATION_EVIDENCE_BUNDLE'] = 'PASS' if candidate_ok else 'FAIL'
        if not candidate_ok:
            reasons.append('EVIDENCE_BUNDLE_MISMATCH')

        approval_ok = True
        if policy.requires_full_approval:
            approval_ok = (
                full_approval is not None
                and full_approval.production_certification_id == production_certification_id
                and full_approval.candidate_fingerprint == candidate_fingerprint
                and full_approval.evidence_bundle_id == evidence_bundle.evidence_bundle_id
                and full_approval.evidence_bundle_fingerprint == evidence_bundle.bundle_fingerprint
                and full_approval.approval_type == 'FULL_APPROVAL'
            )
        checks['FULL_APPROVAL'] = 'PASS' if approval_ok else 'FAIL'
        if not approval_ok:
            reasons.append('FULL_APPROVAL_INVALID')

        stop_ok = (not policy.requires_clear_stop_conditions) or (
            stop_conditions.production_certification_id == production_certification_id
            and stop_conditions.status == 'CLEAR'
        )
        checks['GO_LIVE_STOP_CONDITIONS'] = 'PASS' if stop_ok else 'FAIL'
        if not stop_ok:
            reasons.append('GO_LIVE_STOP_ACTIVE')

        for stage in policy.required_rollout_stages:
            status_fp = rollout_stage_certifications.get(stage)
            ok = bool(status_fp and status_fp[0] == 'PASS' and _SHA256.fullmatch(status_fp[1]))
            checks[f'ROLLOUT_{stage}'] = 'PASS' if ok else 'FAIL'
            if not ok:
                reasons.append(f'ROLLOUT_{stage}_NOT_PASS')

        nonzero = tuple(sorted(k for k, v in hard_zero_metrics.items() if int(v) != 0))
        hard_zero_ok = (not policy.requires_zero_hard_zero_metrics) or not nonzero
        checks['HARD_ZERO_METRICS'] = 'PASS' if hard_zero_ok else 'FAIL'
        if not hard_zero_ok:
            reasons.append('HARD_ZERO_METRIC_NONZERO')

        live_unavailable = not live_postgresql.available or not live_postgresql.executed
        if live_unavailable:
            live_candidate_ok = False
            checks['LIVE_POSTGRES_CANDIDATE_BINDING'] = 'NOT_RUN'
        else:
            live_candidate_ok = live_postgresql.candidate_fingerprint == candidate_fingerprint
            checks['LIVE_POSTGRES_CANDIDATE_BINDING'] = 'PASS' if live_candidate_ok else 'FAIL'
            if not live_candidate_ok:
                reasons.append('LIVE_POSTGRES_CANDIDATE_MISMATCH')

        for code in policy.required_live_postgresql_checks:
            status = str(live_postgresql.check_statuses.get(code, 'NOT_RUN'))
            if status not in {'PASS', 'FAIL', 'BLOCKED', 'NOT_RUN'}:
                status = 'FAIL'
            checks[f'LIVE_POSTGRES_{code}'] = status
            if status == 'FAIL':
                reasons.append(f'LIVE_POSTGRES_{code}_FAILED')
        live_failed = any(checks[f'LIVE_POSTGRES_{code}'] == 'FAIL' for code in policy.required_live_postgresql_checks)
        live_complete = all(checks[f'LIVE_POSTGRES_{code}'] == 'PASS' for code in policy.required_live_postgresql_checks)

        pre_live_failed = any(
            v == 'FAIL' for k, v in checks.items()
            if not k.startswith('LIVE_POSTGRES_') or k == 'LIVE_POSTGRES_CANDIDATE_BINDING'
        )
        if pre_live_failed or live_failed:
            status, verdict = 'FAIL', 'NO_GO'
        elif live_unavailable or not live_complete:
            status, verdict = 'BLOCKED', 'NO_GO'
            reasons.append('LIVE_POSTGRESQL_CERTIFICATION_REQUIRED')
        else:
            status, verdict = 'PASS', 'GO'

        payload = {
            'production_certification_id': str(production_certification_id),
            'candidate_fingerprint': candidate_fingerprint,
            'policy_version': policy.policy_version,
            'status': status,
            'verdict': verdict,
            'reason_codes': sorted(set(reasons)),
            'check_statuses': dict(sorted(checks.items())),
            'live_postgresql_evidence_fingerprint': live_postgresql.evidence_fingerprint,
            'full_approval_fingerprint': full_approval.approval_fingerprint if full_approval else None,
            'evidence_bundle_fingerprint': evidence_bundle.bundle_fingerprint,
        }
        return Milestone7FinalCertificationResult(
            production_certification_id, candidate_fingerprint, policy.policy_version,
            status, verdict, tuple(sorted(set(reasons))), dict(sorted(checks.items())), _hash(payload),
        )


def detect_live_postgresql_capability() -> LivePostgresCertificationEvidence:
    executables = {name: which(name) for name in ('postgres', 'initdb', 'pg_ctl', 'psql')}
    available = all(executables.values())
    statuses: dict[str, str] = {}
    detail = {
        'executables': executables,
        'note': 'Capability detection only. Actual production certification must execute migrations and SQL assertions against PostgreSQL 16+.',
    }
    payload = {'available': available, 'executed': False, 'check_statuses': statuses, 'detail': detail}
    return LivePostgresCertificationEvidence(available, False, statuses, _hash(payload), detail)
