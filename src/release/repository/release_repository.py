from __future__ import annotations
import json
from uuid import UUID
from .models import ReleaseItemRecord, ReleaseManifestRecord, ReleaseRecord

_RELEASE_STATES = {
    'DRAFT','ASSEMBLING','GENERATION_READY','GENERATING','VALIDATING','STAGED','APPROVED',
    'PUBLISHING','PUBLISHED','BLOCKED','PARTIAL_FAILURE','ROLLING_BACK','ROLLED_BACK','CANCELLED'
}
_VARIANTS = {'AGENT','SELLER','PUBLIC'}
_CHANNELS = {'WEB','PDF_DOWNLOAD','PRINT'}


def _hash(value: str | None, field: str) -> None:
    if value is not None and (len(value) != 64 or any(c not in '0123456789abcdef' for c in value)):
        raise ValueError(f'{field} must be lowercase sha256')


class ReleaseRepository:
    INSERT_RELEASE = '''INSERT INTO operations.releases
(release_id,release_name,release_state,release_scope,policy_version,membership_fingerprint,manifest_fingerprint,total_item_count,correlation_id,reason_code,created_by)
VALUES (%s,%s,%s,%s::jsonb,%s,%s,%s,%s,%s,%s,%s)'''
    GET_RELEASE = '''SELECT release_id,release_name,release_state,release_scope,policy_version,membership_fingerprint,manifest_fingerprint,total_item_count,correlation_id,reason_code,created_by,created_at,updated_at
FROM operations.releases WHERE release_id=%s'''
    INSERT_MANIFEST = '''INSERT INTO operations.release_manifests
(release_id,membership_fingerprint,manifest_fingerprint,manifest_payload,frozen_by)
VALUES (%s,%s,%s,%s::jsonb,%s)'''
    GET_MANIFEST = '''SELECT release_id,membership_fingerprint,manifest_fingerprint,manifest_payload,frozen_by,frozen_at
FROM operations.release_manifests WHERE release_id=%s'''
    INSERT_ITEM = '''INSERT INTO operations.release_items
(release_item_id,release_id,property_id,report_variant,channel,membership_ordinal,item_state,target_snapshot_id,target_report_id,target_render_id,target_semantic_fingerprint,target_presentation_fingerprint,last_error_code)
VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)'''
    LIST_ITEMS = '''SELECT release_item_id,release_id,property_id,report_variant,membership_ordinal,channel,item_state,target_snapshot_id,target_report_id,target_render_id,target_semantic_fingerprint,target_presentation_fingerprint,last_error_code
FROM operations.release_items WHERE release_id=%s ORDER BY membership_ordinal'''

    def insert_release(self, cursor, record: ReleaseRecord) -> None:
        if record.release_state not in _RELEASE_STATES:
            raise ValueError('unsupported release state')
        if record.total_item_count < 0:
            raise ValueError('total_item_count must be non-negative')
        _hash(record.membership_fingerprint, 'membership_fingerprint')
        _hash(record.manifest_fingerprint, 'manifest_fingerprint')
        cursor.execute(self.INSERT_RELEASE, (
            record.release_id, record.release_name, record.release_state,
            json.dumps(record.release_scope, separators=(',', ':'), sort_keys=True), record.policy_version,
            record.membership_fingerprint, record.manifest_fingerprint, record.total_item_count,
            record.correlation_id, record.reason_code, record.created_by,
        ))

    def insert_manifest(self, cursor, record: ReleaseManifestRecord) -> None:
        _hash(record.membership_fingerprint, 'membership_fingerprint')
        _hash(record.manifest_fingerprint, 'manifest_fingerprint')
        cursor.execute(self.INSERT_MANIFEST, (
            record.release_id, record.membership_fingerprint, record.manifest_fingerprint,
            json.dumps(record.manifest_payload, separators=(',', ':'), sort_keys=True), record.frozen_by,
        ))

    def insert_item(self, cursor, record: ReleaseItemRecord) -> None:
        if record.report_variant not in _VARIANTS:
            raise ValueError('unsupported report variant')
        if record.channel is not None and record.channel not in _CHANNELS:
            raise ValueError('unsupported publication channel')
        if record.membership_ordinal <= 0:
            raise ValueError('membership_ordinal must be positive')
        if not record.item_state.strip():
            raise ValueError('item_state cannot be blank')
        _hash(record.target_semantic_fingerprint, 'target_semantic_fingerprint')
        _hash(record.target_presentation_fingerprint, 'target_presentation_fingerprint')
        cursor.execute(self.INSERT_ITEM, (
            record.release_item_id, record.release_id, record.property_id, record.report_variant,
            record.channel, record.membership_ordinal, record.item_state, record.target_snapshot_id,
            record.target_report_id, record.target_render_id, record.target_semantic_fingerprint,
            record.target_presentation_fingerprint, record.last_error_code,
        ))
