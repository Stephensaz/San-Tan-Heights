from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

from src.production_certification.certification import (
    FinalCertificationPolicy,
    LivePostgresCertificationEvidence,
    Milestone7FinalCertificationSuite,
    detect_live_postgresql_capability,
)
from src.production_certification.go_live.finalization import (
    CertificationEvidenceBundleBuilder,
    CertificationEvidenceItem,
    FullApprovalIssuer,
    FullApprovalPolicy,
)
from src.production_certification.go_live.stop_conditions import GoLiveStopResult
from src.shared.canonical_json import canonical_json
from hashlib import sha256

ROOT = Path(__file__).resolve().parents[3]
PC = UUID(int=9270)
CAND = 'c' * 64
NOW = datetime(2026, 9, 16, 23, 55, tzinfo=timezone.utc)


def _hash(payload):
    return sha256(canonical_json(payload).encode()).hexdigest()


def _bundle_and_approval():
    full_policy = FullApprovalPolicy.load(ROOT / 'registries/production-certification/full-approval-policy.yaml')
    items = tuple(CertificationEvidenceItem(code, chr(97 + (i % 6)) * 64) for i, code in enumerate(full_policy.required_evidence_codes))
    bundle = CertificationEvidenceBundleBuilder().build(
        production_certification_id=PC,
        candidate_fingerprint=CAND,
        required_codes=full_policy.required_evidence_codes,
        items=items,
        built_by='certifier',
        built_at=NOW,
        evidence_bundle_id=UUID(int=9271),
    )
    stop = GoLiveStopResult(PC, '1.0.0', 'CLEAR', (), 's' * 64, 'ops')
    rollout = {stage: ('PASS', chr(97 + i) * 64) for i, stage in enumerate(full_policy.required_rollout_stages)}
    approval = FullApprovalIssuer().issue(
        policy=full_policy,
        bundle=bundle,
        candidate_fingerprint=CAND,
        stop_conditions=stop,
        rollout_stage_certifications=rollout,
        active_revocations=(),
        approved_by='admin',
        full_approval_id=UUID(int=9272),
        approved_at=NOW,
    )
    return full_policy, bundle, stop, rollout, approval


def _live(status='PASS'):
    policy = FinalCertificationPolicy.load(ROOT / 'registries/production-certification/final-certification-policy.yaml')
    statuses = {code: status for code in policy.required_live_postgresql_checks}
    payload = {'available': True, 'executed': True, 'check_statuses': statuses, 'candidate_fingerprint': CAND, 'source_revision': 'deadbeef'}
    return LivePostgresCertificationEvidence(True, True, statuses, _hash(payload), {'fixture': True}, CAND, 'deadbeef')


def test_m7_027_go_requires_every_production_gate_including_live_postgres():
    _, bundle, stop, rollout, approval = _bundle_and_approval()
    policy = FinalCertificationPolicy.load(ROOT / 'registries/production-certification/final-certification-policy.yaml')
    result = Milestone7FinalCertificationSuite().evaluate(
        policy=policy, production_certification_id=PC, candidate_fingerprint=CAND,
        evidence_bundle=bundle, full_approval=approval, stop_conditions=stop,
        rollout_stage_certifications=rollout, hard_zero_metrics={}, live_postgresql=_live(),
    )
    assert result.status == 'PASS'
    assert result.verdict == 'GO'
    assert not result.reason_codes


def test_m7_027_is_blocked_when_live_postgres_has_not_been_executed():
    _, bundle, stop, rollout, approval = _bundle_and_approval()
    policy = FinalCertificationPolicy.load(ROOT / 'registries/production-certification/final-certification-policy.yaml')
    unavailable = LivePostgresCertificationEvidence(
        False, False, {}, _hash({'available': False, 'executed': False}), {'reason': 'not provisioned'}, None, None
    )
    result = Milestone7FinalCertificationSuite().evaluate(
        policy=policy, production_certification_id=PC, candidate_fingerprint=CAND,
        evidence_bundle=bundle, full_approval=approval, stop_conditions=stop,
        rollout_stage_certifications=rollout, hard_zero_metrics={}, live_postgresql=unavailable,
    )
    assert result.status == 'BLOCKED'
    assert result.verdict == 'NO_GO'
    assert 'LIVE_POSTGRESQL_CERTIFICATION_REQUIRED' in result.reason_codes


def test_m7_027_fails_on_hard_zero_or_rollout_failure_even_if_postgres_passes():
    _, bundle, stop, rollout, approval = _bundle_and_approval()
    policy = FinalCertificationPolicy.load(ROOT / 'registries/production-certification/final-certification-policy.yaml')
    broken = dict(rollout); broken['COHORT_500'] = ('FAIL', 'd' * 64)
    result = Milestone7FinalCertificationSuite().evaluate(
        policy=policy, production_certification_id=PC, candidate_fingerprint=CAND,
        evidence_bundle=bundle, full_approval=approval, stop_conditions=stop,
        rollout_stage_certifications=broken, hard_zero_metrics={'unauthorized_data_exposure': 1}, live_postgresql=_live(),
    )
    assert result.status == 'FAIL'
    assert result.verdict == 'NO_GO'
    assert 'HARD_ZERO_METRIC_NONZERO' in result.reason_codes
    assert 'ROLLOUT_COHORT_500_NOT_PASS' in result.reason_codes



def test_m7_027_rejects_live_postgres_evidence_for_a_different_candidate():
    _, bundle, stop, rollout, approval = _bundle_and_approval()
    policy = FinalCertificationPolicy.load(ROOT / 'registries/production-certification/final-certification-policy.yaml')
    statuses = {code: 'PASS' for code in policy.required_live_postgresql_checks}
    other = 'd' * 64
    payload = {'available': True, 'executed': True, 'check_statuses': statuses, 'candidate_fingerprint': other, 'source_revision': 'deadbeef'}
    live = LivePostgresCertificationEvidence(True, True, statuses, _hash(payload), {'fixture': True}, other, 'deadbeef')
    result = Milestone7FinalCertificationSuite().evaluate(
        policy=policy, production_certification_id=PC, candidate_fingerprint=CAND,
        evidence_bundle=bundle, full_approval=approval, stop_conditions=stop,
        rollout_stage_certifications=rollout, hard_zero_metrics={}, live_postgresql=live,
    )
    assert result.status == 'FAIL'
    assert result.verdict == 'NO_GO'
    assert 'LIVE_POSTGRES_CANDIDATE_MISMATCH' in result.reason_codes

def test_m7_027_local_capability_probe_does_not_claim_execution():
    result = detect_live_postgresql_capability()
    assert result.executed is False
    assert len(result.evidence_fingerprint) == 64
