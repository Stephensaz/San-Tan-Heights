from __future__ import annotations
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Iterable
from uuid import UUID
import yaml
from src.shared.canonical_json import canonical_json
from .tracking import ShadowCycleEvidence
from src.production_certification.audit.sample import ManualAuditSample
from src.production_certification.audit.evidence import ManualAuditEvidence

@dataclass(frozen=True)
class ShadowAcceptancePolicy:
    policy_version: str
    minimum_consecutive_cycles: int
    require_all_targets_pass: bool
    require_latest_cycle_manual_audit: bool
    require_complete_manual_audit_sample: bool
    allowed_manual_audit_statuses_for_acceptance: tuple[str,...]
    require_membership_fingerprint_match: bool

    @classmethod
    def load(cls, path: str | Path) -> 'ShadowAcceptancePolicy':
        data=yaml.safe_load(Path(path).read_text())
        if data.get('status')!='LOCKED': raise ValueError('shadow acceptance policy must be LOCKED')
        minimum=int(data.get('minimum_consecutive_cycles',0))
        allowed=tuple(str(x) for x in (data.get('allowed_manual_audit_statuses_for_acceptance') or ()))
        if minimum < 1 or not allowed: raise ValueError('invalid shadow acceptance policy')
        return cls(str(data['policy_version']),minimum,bool(data.get('require_all_targets_pass',True)),
                   bool(data.get('require_latest_cycle_manual_audit',True)),
                   bool(data.get('require_complete_manual_audit_sample',True)),allowed,
                   bool(data.get('require_membership_fingerprint_match',True)))

@dataclass(frozen=True)
class ShadowAcceptanceResult:
    production_certification_id: UUID
    policy_version: str
    status: str
    reason_codes: tuple[str,...]
    accepted_cycle_ids: tuple[UUID,...]
    latest_shadow_cycle_id: UUID | None
    manual_audit_sample_id: UUID | None
    acceptance_fingerprint: str
    evaluated_by: str

class ShadowAcceptanceEngine:
    def evaluate(self, *, policy: ShadowAcceptancePolicy, production_certification_id: UUID,
                 pilot_membership_fingerprint: str, cycles: Iterable[ShadowCycleEvidence],
                 manual_audit_sample: ManualAuditSample | None,
                 manual_audit_evidence: Iterable[ManualAuditEvidence], evaluated_by: str) -> ShadowAcceptanceResult:
        if not evaluated_by.strip(): raise ValueError('evaluated_by is required')
        rows=sorted((c for c in cycles if c.production_certification_id==production_certification_id),key=lambda c:c.cycle_number)
        reasons=[]
        if len({c.cycle_number for c in rows}) != len(rows): raise ValueError('duplicate shadow cycle number')
        if policy.require_membership_fingerprint_match and any(c.pilot_membership_fingerprint!=pilot_membership_fingerprint for c in rows):
            reasons.append('SHADOW_MEMBERSHIP_DRIFT')
        passing=[]
        for c in reversed(rows):
            if c.cycle_status!='PASS': break
            if policy.require_all_targets_pass and c.failed_target_count != 0: break
            passing.append(c)
        passing=tuple(reversed(passing[:policy.minimum_consecutive_cycles]))
        if len(passing) < policy.minimum_consecutive_cycles:
            reasons.append('INSUFFICIENT_CONSECUTIVE_PASS_CYCLES')
        latest=rows[-1] if rows else None
        audit_rows=tuple(manual_audit_evidence)
        if policy.require_latest_cycle_manual_audit:
            if latest is None or manual_audit_sample is None or manual_audit_sample.shadow_cycle_id != latest.shadow_cycle_id:
                reasons.append('LATEST_CYCLE_MANUAL_AUDIT_MISSING')
        if manual_audit_sample is not None:
            by_property={x.property_id:x for x in audit_rows if x.manual_audit_sample_id==manual_audit_sample.manual_audit_sample_id}
            if len(by_property) != len([x for x in audit_rows if x.manual_audit_sample_id==manual_audit_sample.manual_audit_sample_id]):
                raise ValueError('duplicate manual audit evidence for property')
            if policy.require_complete_manual_audit_sample and set(by_property) != set(manual_audit_sample.sampled_property_ids):
                reasons.append('MANUAL_AUDIT_SAMPLE_INCOMPLETE')
            if any(x.audit_status not in policy.allowed_manual_audit_statuses_for_acceptance for x in by_property.values()):
                reasons.append('MANUAL_AUDIT_NOT_ALL_PASS')
        elif policy.require_latest_cycle_manual_audit:
            reasons.append('MANUAL_AUDIT_SAMPLE_MISSING')
        status='PASS' if not reasons else 'FAIL'
        payload={'production_certification_id':str(production_certification_id),'policy_version':policy.policy_version,
                 'pilot_membership_fingerprint':pilot_membership_fingerprint,'status':status,
                 'reason_codes':sorted(set(reasons)),'accepted_cycle_ids':[str(x.shadow_cycle_id) for x in passing],
                 'latest_shadow_cycle_id':str(latest.shadow_cycle_id) if latest else None,
                 'manual_audit_sample_id':str(manual_audit_sample.manual_audit_sample_id) if manual_audit_sample else None,
                 'manual_audit_evidence_hashes':sorted(x.evidence_hash for x in audit_rows)}
        fp=sha256(canonical_json(payload).encode()).hexdigest()
        return ShadowAcceptanceResult(production_certification_id,policy.policy_version,status,tuple(sorted(set(reasons))),
             tuple(x.shadow_cycle_id for x in passing), latest.shadow_cycle_id if latest else None,
             manual_audit_sample.manual_audit_sample_id if manual_audit_sample else None,fp,evaluated_by)
