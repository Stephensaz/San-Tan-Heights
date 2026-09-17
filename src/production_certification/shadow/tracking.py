from __future__ import annotations
from dataclasses import dataclass
from hashlib import sha256
from typing import Mapping, Any
from uuid import UUID, uuid4
import re
from src.shared.canonical_json import canonical_json
from .orchestrator import ShadowRunResult, ShadowTargetResult

_SHA = re.compile(r'^[0-9a-f]{64}$')

@dataclass(frozen=True)
class ShadowCycleTargetEvidence:
    property_id: UUID
    variant: str
    status: str
    generated_fingerprint: str | None
    comparison_fingerprint: str | None
    detail: Mapping[str, Any]
    target_evidence_hash: str

@dataclass(frozen=True)
class ShadowCycleEvidence:
    shadow_cycle_id: UUID
    production_certification_id: UUID
    cycle_number: int
    policy_version: str
    pilot_membership_fingerprint: str
    target_count: int
    passed_target_count: int
    failed_target_count: int
    cycle_status: str
    orchestrator_evidence_hash: str
    cycle_fingerprint: str
    recorded_by: str
    target_results: tuple[ShadowCycleTargetEvidence, ...]

class ShadowCycleTracker:
    @staticmethod
    def _hash(payload: Any) -> str:
        return sha256(canonical_json(payload).encode('utf-8')).hexdigest()

    def capture(self, *, cycle_number: int, run_result: ShadowRunResult, recorded_by: str,
                shadow_cycle_id: UUID | None = None) -> ShadowCycleEvidence:
        if cycle_number < 1:
            raise ValueError('cycle_number must be >= 1')
        if not recorded_by.strip():
            raise ValueError('recorded_by is required')
        if not _SHA.fullmatch(run_result.membership_fingerprint) or not _SHA.fullmatch(run_result.evidence_hash):
            raise ValueError('shadow run fingerprints must be lowercase SHA-256')
        ordered=tuple(sorted(run_result.target_results,key=lambda r:(str(r.property_id),r.variant)))
        if len({(r.property_id,r.variant) for r in ordered}) != len(ordered):
            raise ValueError('duplicate shadow target result')
        targets=[]
        for r in ordered:
            if r.status not in {'PASS','FAIL'}:
                raise ValueError('unknown shadow target status')
            payload={
                'property_id':str(r.property_id),'variant':r.variant,'status':r.status,
                'generated_fingerprint':r.generated_fingerprint,
                'comparison_fingerprint':r.comparison_fingerprint,
                'detail':dict(r.detail),
            }
            targets.append(ShadowCycleTargetEvidence(r.property_id,r.variant,r.status,
                           r.generated_fingerprint,r.comparison_fingerprint,dict(r.detail),self._hash(payload)))
        passed=sum(x.status=='PASS' for x in targets); failed=sum(x.status=='FAIL' for x in targets)
        status='PASS' if targets and failed==0 and run_result.status=='PASS' else 'FAIL'
        cycle_payload={
            'production_certification_id':str(run_result.production_certification_id),
            'cycle_number':cycle_number,'policy_version':run_result.policy_version,
            'pilot_membership_fingerprint':run_result.membership_fingerprint,
            'orchestrator_evidence_hash':run_result.evidence_hash,'cycle_status':status,
            'targets':[{'property_id':str(x.property_id),'variant':x.variant,
                        'status':x.status,'target_evidence_hash':x.target_evidence_hash} for x in targets],
        }
        return ShadowCycleEvidence(shadow_cycle_id or uuid4(),run_result.production_certification_id,
            cycle_number,run_result.policy_version,run_result.membership_fingerprint,len(targets),passed,failed,
            status,run_result.evidence_hash,self._hash(cycle_payload),recorded_by,tuple(targets))
