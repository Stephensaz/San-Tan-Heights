from __future__ import annotations
from dataclasses import dataclass
from uuid import UUID, uuid4
from src.shared.hash import sha256_canonical
from src.release.membership.resolver import MembershipResolution, ReleaseScope
from src.release.policy.registry import ReleasePolicy
from src.release.repository.models import ReleaseItemRecord, ReleaseManifestRecord

@dataclass(frozen=True)
class FrozenReleaseManifest:
    release_id: UUID
    policy_id: str
    policy_version: str
    membership_fingerprint: str
    manifest_fingerprint: str
    total_item_count: int
    manifest_payload: dict
    items: tuple[ReleaseItemRecord,...]

class ReleaseManifestFreezer:
    def build(self, *, release_id: UUID, policy: ReleasePolicy, scope: ReleaseScope, resolution: MembershipResolution, frozen_by='RELEASE_SERVICE') -> FrozenReleaseManifest:
        member_payload=[]; items=[]
        for m in resolution.members:
            c=m.candidate
            member_payload.append({
                'membership_ordinal':m.membership_ordinal,'property_id':str(c.property_id),'report_variant':c.report_variant,'channel':c.channel,
                'target_snapshot_id':str(c.target_snapshot_id) if c.target_snapshot_id else None,
                'target_report_id':str(c.target_report_id) if c.target_report_id else None,
                'target_render_id':str(c.target_render_id) if c.target_render_id else None,
                'target_semantic_fingerprint':c.target_semantic_fingerprint,
                'target_presentation_fingerprint':c.target_presentation_fingerprint,
            })
            items.append(ReleaseItemRecord(uuid4(),release_id,c.property_id,c.report_variant,m.membership_ordinal,c.channel,'PENDING',c.target_snapshot_id,c.target_report_id,c.target_render_id,c.target_semantic_fingerprint,c.target_presentation_fingerprint,None))
        scope_payload={
            'property_ids': sorted(str(v) for v in scope.property_ids) if scope.property_ids is not None else None,
            'variants': sorted(scope.variants) if scope.variants is not None else None,
            'channels': sorted(scope.channels) if scope.channels is not None else None,
        }
        payload={'release_id':str(release_id),'policy_id':policy.policy_id,'policy_registry_id':policy.registry_id,'policy_version':policy.version,'scope':scope_payload,'membership_fingerprint':resolution.membership_fingerprint,'members':member_payload}
        fingerprint=sha256_canonical(payload)
        return FrozenReleaseManifest(release_id,policy.policy_id,policy.version,resolution.membership_fingerprint,fingerprint,len(items),payload,tuple(items))

    def persist(self, cursor, repository, frozen: FrozenReleaseManifest, *, frozen_by='RELEASE_SERVICE') -> None:
        # Caller owns the transaction. Lock parent to serialize freeze attempts.
        cursor.execute('SELECT release_id FROM operations.releases WHERE release_id=%s FOR UPDATE',(frozen.release_id,))
        if cursor.fetchone() is None: raise ValueError('release not found')
        cursor.execute('SELECT manifest_fingerprint FROM operations.release_manifests WHERE release_id=%s',(frozen.release_id,))
        existing=cursor.fetchone()
        if existing is not None:
            existing_fp=existing[0] if not isinstance(existing,dict) else existing['manifest_fingerprint']
            if existing_fp==frozen.manifest_fingerprint: return
            raise ValueError('release manifest already frozen with different fingerprint')
        for item in frozen.items: repository.insert_item(cursor,item)
        repository.insert_manifest(cursor,ReleaseManifestRecord(frozen.release_id,frozen.membership_fingerprint,frozen.manifest_fingerprint,frozen.manifest_payload,frozen_by))
        cursor.execute('''UPDATE operations.releases SET policy_version=%s,membership_fingerprint=%s,manifest_fingerprint=%s,total_item_count=%s,updated_at=now() WHERE release_id=%s''',(frozen.policy_version,frozen.membership_fingerprint,frozen.manifest_fingerprint,frozen.total_item_count,frozen.release_id))
