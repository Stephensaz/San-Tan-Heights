from __future__ import annotations
from dataclasses import dataclass
from uuid import UUID
from src.shared.hash import sha256_canonical
from src.release.policy.registry import ReleasePolicy

@dataclass(frozen=True)
class ReleaseScope:
    property_ids: frozenset[UUID] | None = None
    variants: frozenset[str] | None = None
    channels: frozenset[str] | None = None

@dataclass(frozen=True)
class ReleaseCandidate:
    property_id: UUID
    report_variant: str
    channel: str | None = None
    target_snapshot_id: UUID | None = None
    target_report_id: UUID | None = None
    target_render_id: UUID | None = None
    target_semantic_fingerprint: str | None = None
    target_presentation_fingerprint: str | None = None

@dataclass(frozen=True)
class ResolvedMember:
    membership_ordinal: int
    candidate: ReleaseCandidate

@dataclass(frozen=True)
class MembershipResolution:
    members: tuple[ResolvedMember,...]
    membership_fingerprint: str

class DeterministicMembershipResolver:
    @staticmethod
    def _validate_hash(value: str | None, field: str):
        if value is not None and (len(value)!=64 or any(c not in '0123456789abcdef' for c in value)):
            raise ValueError(f'{field} must be lowercase sha256')
    def resolve(self, *, candidates, policy: ReleasePolicy, scope: ReleaseScope=ReleaseScope()) -> MembershipResolution:
        by_key={}
        for c in candidates:
            if c.report_variant not in policy.allowed_variants: raise ValueError(f'variant not allowed by policy: {c.report_variant}')
            if c.channel is None and not policy.channel_optional: raise ValueError('channel required by release policy')
            if c.channel is not None and c.channel not in policy.allowed_channels: raise ValueError(f'channel not allowed by policy: {c.channel}')
            self._validate_hash(c.target_semantic_fingerprint,'target_semantic_fingerprint'); self._validate_hash(c.target_presentation_fingerprint,'target_presentation_fingerprint')
            if scope.property_ids is not None and c.property_id not in scope.property_ids: continue
            if scope.variants is not None and c.report_variant not in scope.variants: continue
            if scope.channels is not None and c.channel not in scope.channels: continue
            key=(str(c.property_id),c.report_variant,c.channel or '')
            previous=by_key.get(key)
            if previous is not None and previous!=c: raise ValueError(f'conflicting duplicate release candidate: {key}')
            by_key[key]=c
        ordered=[by_key[k] for k in sorted(by_key)]
        members=tuple(ResolvedMember(i+1,c) for i,c in enumerate(ordered))
        payload=[{'property_id':str(m.candidate.property_id),'report_variant':m.candidate.report_variant,'channel':m.candidate.channel} for m in members]
        return MembershipResolution(members,sha256_canonical(payload))
