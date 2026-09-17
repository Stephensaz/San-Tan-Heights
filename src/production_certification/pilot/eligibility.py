from __future__ import annotations
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Iterable
from uuid import UUID
import yaml
from src.shared.canonical_json import canonical_json

@dataclass(frozen=True)
class PilotEligibilityPolicy:
    policy_version: str
    required_identity_status: str
    required_snapshot_qa_status: str
    allowed_snapshot_completeness: tuple[str,...]
    blocking_incident_severities: tuple[str,...]
    blocking_publication_freeze: bool
    max_pilot_properties: int
    variants: tuple[str,...]

    @classmethod
    def load(cls, path: str | Path) -> 'PilotEligibilityPolicy':
        data=yaml.safe_load(Path(path).read_text())
        if data.get('status')!='LOCKED': raise ValueError('pilot eligibility policy must be LOCKED')
        max_props=int(data.get('max_pilot_properties',0))
        variants=tuple(data.get('variants') or ())
        if max_props < 1 or not variants: raise ValueError('invalid pilot eligibility policy')
        return cls(str(data['policy_version']),str(data['required_identity_status']),str(data['required_snapshot_qa_status']),
                   tuple(data.get('allowed_snapshot_completeness') or ()),tuple(data.get('blocking_incident_severities') or ()),
                   bool(data.get('blocking_publication_freeze',True)),max_props,variants)

@dataclass(frozen=True)
class PilotPropertyCandidate:
    property_id: UUID
    identity_status: str
    snapshot_id: UUID | None
    snapshot_qa_status: str
    snapshot_completeness: str
    open_incident_severities: tuple[str,...]=()
    publication_frozen: bool=False

@dataclass(frozen=True)
class PilotPropertyDecision:
    property_id: UUID
    eligible: bool
    reason_codes: tuple[str,...]
    snapshot_id: UUID | None

@dataclass(frozen=True)
class PilotEligibilityResult:
    policy_version: str
    selected_property_ids: tuple[UUID,...]
    decisions: tuple[PilotPropertyDecision,...]
    membership_fingerprint: str

class RealPropertyPilotEligibilityResolver:
    def resolve(self, *, policy: PilotEligibilityPolicy, candidates: Iterable[PilotPropertyCandidate]) -> PilotEligibilityResult:
        rows=sorted(candidates,key=lambda x:str(x.property_id))
        if len({x.property_id for x in rows}) != len(rows): raise ValueError('duplicate pilot property candidate')
        decisions=[]; eligible=[]
        for c in rows:
            reasons=[]
            if c.identity_status != policy.required_identity_status: reasons.append('IDENTITY_NOT_RESOLVED')
            if c.snapshot_id is None: reasons.append('CURRENT_SNAPSHOT_MISSING')
            if c.snapshot_qa_status != policy.required_snapshot_qa_status: reasons.append('SNAPSHOT_QA_NOT_PASS')
            if c.snapshot_completeness not in policy.allowed_snapshot_completeness: reasons.append('SNAPSHOT_COMPLETENESS_NOT_ELIGIBLE')
            if set(c.open_incident_severities).intersection(policy.blocking_incident_severities): reasons.append('BLOCKING_INCIDENT_OPEN')
            if policy.blocking_publication_freeze and c.publication_frozen: reasons.append('PUBLICATION_FROZEN')
            ok=not reasons
            decisions.append(PilotPropertyDecision(c.property_id,ok,tuple(sorted(reasons)),c.snapshot_id))
            if ok: eligible.append(c.property_id)
        selected=tuple(eligible[:policy.max_pilot_properties])
        selected_set=set(selected)
        # Eligible but beyond the locked cap remain non-selected with explicit evidence.
        decisions=tuple(PilotPropertyDecision(d.property_id, d.eligible and d.property_id in selected_set,
                       d.reason_codes if d.property_id in selected_set or not d.eligible else ('PILOT_CAP_EXCEEDED',), d.snapshot_id)
                       for d in decisions)
        payload={'policy_version':policy.policy_version,'property_ids':[str(x) for x in selected]}
        fp=sha256(canonical_json(payload).encode('utf-8')).hexdigest()
        return PilotEligibilityResult(policy.policy_version,selected,decisions,fp)
