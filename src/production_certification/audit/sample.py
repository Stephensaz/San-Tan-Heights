from __future__ import annotations
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Iterable
from uuid import UUID, uuid4
import yaml
from src.shared.canonical_json import canonical_json
from src.production_certification.shadow.tracking import ShadowCycleEvidence

@dataclass(frozen=True)
class ManualAuditPolicy:
    policy_version: str
    sample_size: int
    selection_strategy: str
    allowed_audit_statuses: tuple[str,...]
    checklist_version: str

    @classmethod
    def load(cls, path: str | Path) -> 'ManualAuditPolicy':
        data=yaml.safe_load(Path(path).read_text())
        if data.get('status')!='LOCKED': raise ValueError('manual audit policy must be LOCKED')
        size=int(data.get('sample_size',0))
        if size < 1: raise ValueError('sample_size must be >= 1')
        strategy=str(data.get('selection_strategy',''))
        if strategy!='FAILED_SHADOW_FIRST_THEN_DETERMINISTIC_HASH': raise ValueError('unsupported audit selection strategy')
        statuses=tuple(data.get('allowed_audit_statuses') or ())
        if set(statuses)!={'PASS','FAIL','REVIEW_REQUIRED'}: raise ValueError('invalid audit statuses')
        checklist=str(data.get('checklist_version',''))
        if not checklist.strip(): raise ValueError('checklist_version is required')
        return cls(str(data['policy_version']),size,strategy,statuses,checklist)

@dataclass(frozen=True)
class ManualAuditSample:
    manual_audit_sample_id: UUID
    production_certification_id: UUID
    shadow_cycle_id: UUID
    policy_version: str
    sampled_property_ids: tuple[UUID,...]
    failed_shadow_property_ids: tuple[UUID,...]
    sample_fingerprint: str
    built_by: str

class ManualAuditSampleBuilder:
    @staticmethod
    def _rank(*, production_certification_id: UUID, shadow_cycle_id: UUID, policy_version: str, property_id: UUID) -> str:
        payload={'production_certification_id':str(production_certification_id),'shadow_cycle_id':str(shadow_cycle_id),
                 'policy_version':policy_version,'property_id':str(property_id)}
        return sha256(canonical_json(payload).encode('utf-8')).hexdigest()

    def build(self, *, policy: ManualAuditPolicy, shadow_cycle: ShadowCycleEvidence,
              pilot_property_ids: Iterable[UUID], built_by: str,
              manual_audit_sample_id: UUID | None=None) -> ManualAuditSample:
        if not built_by.strip(): raise ValueError('built_by is required')
        pilot=tuple(sorted(set(pilot_property_ids),key=str))
        if not pilot: raise ValueError('pilot population is empty')
        target_properties={x.property_id for x in shadow_cycle.target_results}
        if not target_properties.issubset(set(pilot)):
            raise ValueError('shadow cycle contains property outside frozen pilot membership')
        failed=tuple(sorted({x.property_id for x in shadow_cycle.target_results if x.status=='FAIL'},key=str))
        failed_ranked=tuple(sorted(failed,key=lambda p:self._rank(production_certification_id=shadow_cycle.production_certification_id,
                            shadow_cycle_id=shadow_cycle.shadow_cycle_id,policy_version=policy.policy_version,property_id=p)))
        remaining=[p for p in pilot if p not in set(failed)]
        remaining.sort(key=lambda p:self._rank(production_certification_id=shadow_cycle.production_certification_id,
                       shadow_cycle_id=shadow_cycle.shadow_cycle_id,policy_version=policy.policy_version,property_id=p))
        sampled=tuple((list(failed_ranked)+remaining)[:min(policy.sample_size,len(pilot))])
        payload={'production_certification_id':str(shadow_cycle.production_certification_id),
                 'shadow_cycle_id':str(shadow_cycle.shadow_cycle_id),'policy_version':policy.policy_version,
                 'sampled_property_ids':[str(x) for x in sampled]}
        fp=sha256(canonical_json(payload).encode('utf-8')).hexdigest()
        return ManualAuditSample(manual_audit_sample_id or uuid4(),shadow_cycle.production_certification_id,
            shadow_cycle.shadow_cycle_id,policy.policy_version,sampled,failed,fp,built_by)
