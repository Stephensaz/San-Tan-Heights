from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
from uuid import UUID, uuid4
import yaml
from src.shared.canonical_json import canonical_json
from src.production_certification.shadow.acceptance import ShadowAcceptanceResult
from src.production_certification.go_live.stop_conditions import GoLiveStopResult

@dataclass(frozen=True)
class LimitedApprovalPolicy:
    policy_version: str
    approval_type: str
    max_duration_hours: int
    max_properties: int
    allowed_variants: tuple[str,...]
    requires_shadow_acceptance: bool
    requires_stop_condition_clearance: bool
    prohibits_full_approval_inference: bool
    @classmethod
    def load(cls,path:str|Path)->'LimitedApprovalPolicy':
        d=yaml.safe_load(Path(path).read_text())
        if d.get('status')!='LOCKED' or d.get('approval_type')!='LIMITED': raise ValueError('limited approval policy must be LOCKED/LIMITED')
        hours=int(d.get('max_duration_hours',0)); max_props=int(d.get('max_properties',0)); variants=tuple(d.get('allowed_variants') or ())
        if hours<1 or max_props<1 or not variants: raise ValueError('invalid limited approval policy')
        return cls(str(d['policy_version']),'LIMITED',hours,max_props,tuple(str(x) for x in variants),
                   bool(d.get('requires_shadow_acceptance',True)),bool(d.get('requires_stop_condition_clearance',True)),
                   bool(d.get('prohibits_full_approval_inference',True)))

@dataclass(frozen=True)
class LimitedApproval:
    limited_approval_id: UUID
    production_certification_id: UUID
    policy_version: str
    candidate_fingerprint: str
    pilot_membership_fingerprint: str
    max_properties: int
    allowed_variants: tuple[str,...]
    shadow_acceptance_fingerprint: str
    stop_condition_fingerprint: str
    issued_at: datetime
    expires_at: datetime
    approval_fingerprint: str
    approved_by: str
    approval_type: str='LIMITED'

class LimitedApprovalIssuer:
    def issue(self, *, policy: LimitedApprovalPolicy, production_certification_id: UUID,
              candidate_fingerprint: str, pilot_membership_fingerprint: str,
              shadow_acceptance: ShadowAcceptanceResult, stop_conditions: GoLiveStopResult,
              approved_by: str, issued_at: datetime | None=None, limited_approval_id: UUID | None=None) -> LimitedApproval:
        if not approved_by.strip(): raise ValueError('approved_by is required')
        if shadow_acceptance.production_certification_id != production_certification_id or stop_conditions.production_certification_id != production_certification_id:
            raise ValueError('certification identity mismatch')
        if policy.requires_shadow_acceptance and shadow_acceptance.status!='PASS': raise ValueError('shadow acceptance has not passed')
        if policy.requires_stop_condition_clearance and stop_conditions.status!='CLEAR': raise ValueError('go-live stop conditions are not clear')
        now=issued_at or datetime.now(timezone.utc)
        if now.tzinfo is None: raise ValueError('issued_at must be timezone-aware')
        expires=now+timedelta(hours=policy.max_duration_hours)
        aid=limited_approval_id or uuid4()
        payload={'limited_approval_id':str(aid),'production_certification_id':str(production_certification_id),
                 'policy_version':policy.policy_version,'approval_type':'LIMITED','candidate_fingerprint':candidate_fingerprint,
                 'pilot_membership_fingerprint':pilot_membership_fingerprint,'max_properties':policy.max_properties,
                 'allowed_variants':list(policy.allowed_variants),'shadow_acceptance_fingerprint':shadow_acceptance.acceptance_fingerprint,
                 'stop_condition_fingerprint':stop_conditions.evidence_fingerprint,'issued_at':now.isoformat(),'expires_at':expires.isoformat()}
        fp=sha256(canonical_json(payload).encode()).hexdigest()
        return LimitedApproval(aid,production_certification_id,policy.policy_version,candidate_fingerprint,pilot_membership_fingerprint,
             policy.max_properties,policy.allowed_variants,shadow_acceptance.acceptance_fingerprint,stop_conditions.evidence_fingerprint,
             now,expires,fp,approved_by)
