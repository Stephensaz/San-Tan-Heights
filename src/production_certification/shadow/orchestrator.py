from __future__ import annotations
from dataclasses import dataclass
from hashlib import sha256
from typing import Protocol, Iterable, Mapping, Any
from uuid import UUID
from src.shared.canonical_json import canonical_json

class ShadowExecutor(Protocol):
    # Deliberately no publish/promote/pointer mutation operation in this interface.
    def generate(self, *, property_id: UUID, variant: str) -> Mapping[str,Any]: ...
    def compare_current(self, *, property_id: UUID, variant: str, generated: Mapping[str,Any]) -> Mapping[str,Any]: ...

@dataclass(frozen=True)
class ShadowTarget:
    property_id: UUID
    variant: str

@dataclass(frozen=True)
class ShadowTargetResult:
    property_id: UUID
    variant: str
    status: str
    generated_fingerprint: str | None
    comparison_fingerprint: str | None
    detail: Mapping[str,Any]

@dataclass(frozen=True)
class ShadowRunResult:
    production_certification_id: UUID
    policy_version: str
    membership_fingerprint: str
    status: str
    target_results: tuple[ShadowTargetResult,...]
    evidence_hash: str

class ShadowModeOrchestrator:
    ALLOWED_VARIANTS=frozenset({'AGENT','SELLER','PUBLIC'})
    def run(self, *, production_certification_id: UUID, policy_version: str,
            selected_property_ids: Iterable[UUID], membership_fingerprint: str,
            variants: Iterable[str], executor: ShadowExecutor,
            publication_mutation_allowed: bool=False) -> ShadowRunResult:
        if publication_mutation_allowed:
            raise ValueError('shadow mode cannot allow publication mutation')
        if len(membership_fingerprint)!=64:
            raise ValueError('membership_fingerprint must be sha256')
        variants=tuple(variants)
        if not variants or any(v not in self.ALLOWED_VARIANTS for v in variants):
            raise ValueError('invalid shadow variants')
        targets=tuple(ShadowTarget(pid,v) for pid in sorted(set(selected_property_ids),key=str) for v in variants)
        results=[]
        for target in targets:
            try:
                generated=dict(executor.generate(property_id=target.property_id,variant=target.variant))
                comparison=dict(executor.compare_current(property_id=target.property_id,variant=target.variant,generated=generated))
                gen_fp=sha256(canonical_json(generated).encode()).hexdigest()
                cmp_fp=sha256(canonical_json(comparison).encode()).hexdigest()
                results.append(ShadowTargetResult(target.property_id,target.variant,'PASS',gen_fp,cmp_fp,comparison))
            except Exception as exc:
                results.append(ShadowTargetResult(target.property_id,target.variant,'FAIL',None,None,{'error_type':type(exc).__name__}))
        status='PASS' if results and all(r.status=='PASS' for r in results) else 'FAIL'
        evidence_payload={
            'production_certification_id':str(production_certification_id),'policy_version':policy_version,
            'membership_fingerprint':membership_fingerprint,
            'targets':[{'property_id':str(r.property_id),'variant':r.variant,'status':r.status,
                        'generated_fingerprint':r.generated_fingerprint,'comparison_fingerprint':r.comparison_fingerprint}
                       for r in results]
        }
        evidence_hash=sha256(canonical_json(evidence_payload).encode()).hexdigest()
        return ShadowRunResult(production_certification_id,policy_version,membership_fingerprint,status,tuple(results),evidence_hash)
