from __future__ import annotations
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Mapping
from uuid import UUID
import yaml
from src.shared.canonical_json import canonical_json

@dataclass(frozen=True)
class GoLiveStopPolicy:
    policy_version: str
    blocking_conditions: tuple[str,...]
    @classmethod
    def load(cls,path:str|Path)->'GoLiveStopPolicy':
        data=yaml.safe_load(Path(path).read_text())
        if data.get('status')!='LOCKED': raise ValueError('go-live stop policy must be LOCKED')
        conditions=tuple(str(x) for x in (data.get('blocking_conditions') or ()))
        if not conditions or len(set(conditions))!=len(conditions): raise ValueError('invalid go-live stop policy')
        return cls(str(data['policy_version']),conditions)

@dataclass(frozen=True)
class GoLiveObservedState:
    environment_parity_status: str
    production_configuration_status: str
    shadow_acceptance_status: str
    hard_zero_nonzero_count: int
    open_critical_incident_count: int
    global_publication_freeze_active: bool
    candidate_revoked: bool
    expected_candidate_fingerprint: str
    observed_candidate_fingerprint: str

@dataclass(frozen=True)
class GoLiveStopResult:
    production_certification_id: UUID
    policy_version: str
    status: str
    blocking_conditions: tuple[str,...]
    evidence_fingerprint: str
    evaluated_by: str

class GoLiveStopConditionEngine:
    def evaluate(self, *, production_certification_id: UUID, policy: GoLiveStopPolicy,
                 observed: GoLiveObservedState, evaluated_by: str) -> GoLiveStopResult:
        if not evaluated_by.strip(): raise ValueError('evaluated_by is required')
        active=[]
        checks={
          'ENVIRONMENT_PARITY_NOT_PASS': observed.environment_parity_status!='PASS',
          'PRODUCTION_CONFIGURATION_NOT_PASS': observed.production_configuration_status!='PASS',
          'SHADOW_ACCEPTANCE_NOT_PASS': observed.shadow_acceptance_status!='PASS',
          'HARD_ZERO_METRIC_NONZERO': observed.hard_zero_nonzero_count!=0,
          'OPEN_CRITICAL_INCIDENT': observed.open_critical_incident_count!=0,
          'GLOBAL_PUBLICATION_FREEZE_ACTIVE': observed.global_publication_freeze_active,
          'CANDIDATE_REVOKED': observed.candidate_revoked,
          'CANDIDATE_FINGERPRINT_MISMATCH': observed.expected_candidate_fingerprint!=observed.observed_candidate_fingerprint,
        }
        unknown=set(policy.blocking_conditions)-set(checks)
        if unknown: raise ValueError(f'unsupported stop conditions: {sorted(unknown)}')
        active=tuple(sorted(k for k in policy.blocking_conditions if checks[k]))
        status='CLEAR' if not active else 'STOP'
        payload={'production_certification_id':str(production_certification_id),'policy_version':policy.policy_version,
                 'status':status,'blocking_conditions':list(active),'observed':{
                   'environment_parity_status':observed.environment_parity_status,
                   'production_configuration_status':observed.production_configuration_status,
                   'shadow_acceptance_status':observed.shadow_acceptance_status,
                   'hard_zero_nonzero_count':observed.hard_zero_nonzero_count,
                   'open_critical_incident_count':observed.open_critical_incident_count,
                   'global_publication_freeze_active':observed.global_publication_freeze_active,
                   'candidate_revoked':observed.candidate_revoked,
                   'expected_candidate_fingerprint':observed.expected_candidate_fingerprint,
                   'observed_candidate_fingerprint':observed.observed_candidate_fingerprint}}
        fp=sha256(canonical_json(payload).encode()).hexdigest()
        return GoLiveStopResult(production_certification_id,policy.policy_version,status,active,fp,evaluated_by)
