from __future__ import annotations
from uuid import UUID
from .models import ReportVersion, ReportDependency

class ReportRepository:
    LOCK_TARGET="""SELECT pg_advisory_xact_lock(hashtextextended(%s,0))"""
    INSERT_REPORT='''INSERT INTO reporting.report_versions
(report_id,property_id,report_variant,version_number,snapshot_id,report_schema_version,content_contract_version,variant_policy_version,builder_version,report_input_hash,canonical_payload_hash,stored_payload_hash,canonical_payload,dependency_manifest_hash,generation_reason,content_state,health_state,qa_status,qa_completed_at,publication_eligible,supersedes_report_id,superseded_by_report_id,created_by)
VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)'''
    INSERT_DEP='''INSERT INTO reporting.report_dependencies
(report_dependency_id,report_id,dependency_type,dependency_id,semantic_fingerprint,dependency_version,source_snapshot_id)
VALUES (%s,%s,%s,%s,%s,%s,%s)'''
    FIND_EQUIVALENT='''SELECT report_id FROM reporting.report_versions
WHERE property_id=%s AND report_variant=%s AND report_input_hash=%s
AND content_state NOT IN ('FAILED','STALE','INVALIDATED','ARCHIVED')
ORDER BY version_number DESC LIMIT 1'''
    INSERT_DIFF='''INSERT INTO reporting.report_diffs (report_diff_id,old_report_id,new_report_id,diff_payload,diff_hash) VALUES (%s,%s,%s,%s,%s) ON CONFLICT (old_report_id,new_report_id) DO NOTHING'''
    MARK_VALIDATING='''UPDATE reporting.report_versions SET content_state='VALIDATING' WHERE report_id=%s AND content_state='BUILDING' RETURNING report_id'''
    MARK_READY='''UPDATE reporting.report_versions SET content_state='READY',health_state='CLEAN',qa_status='PASS',qa_completed_at=now(),publication_eligible=true WHERE report_id=%s AND content_state IN ('BUILDING','VALIDATING') RETURNING report_id'''
    FIND_BY_ID='''SELECT report_id,property_id,report_variant,version_number,snapshot_id,report_schema_version,content_contract_version,variant_policy_version,builder_version,report_input_hash,canonical_payload_hash,stored_payload_hash,canonical_payload,dependency_manifest_hash,generation_reason,content_state,health_state,qa_status,qa_completed_at,publication_eligible,supersedes_report_id,superseded_by_report_id,created_at,created_by FROM reporting.report_versions WHERE report_id=%s'''

    @staticmethod
    def _hash64(value: str, field: str):
        if len(value)!=64 or any(c not in '0123456789abcdef' for c in value):
            raise ValueError(f'{field} must be a lowercase SHA-256 hex digest')


    def lock_target(self,cursor,property_id: UUID,report_variant: str)->None:
        if report_variant not in {'AGENT','SELLER','PUBLIC'}: raise ValueError('unsupported report variant')
        cursor.execute(self.LOCK_TARGET,(f'{property_id}:{report_variant}',))

    def insert_report(self,cursor,report: ReportVersion)->None:
        if report.report_variant not in {'AGENT','SELLER','PUBLIC'}: raise ValueError('unsupported report variant')
        if report.version_number < 1: raise ValueError('version_number must be positive')
        for name,value in [('report_input_hash',report.report_input_hash),('canonical_payload_hash',report.canonical_payload_hash),('dependency_manifest_hash',report.dependency_manifest_hash)]: self._hash64(value,name)
        if report.stored_payload_hash is not None: self._hash64(report.stored_payload_hash,'stored_payload_hash')
        cursor.execute(self.INSERT_REPORT,(report.report_id,report.property_id,report.report_variant,report.version_number,report.snapshot_id,report.report_schema_version,report.content_contract_version,report.variant_policy_version,report.builder_version,report.report_input_hash,report.canonical_payload_hash,report.stored_payload_hash,report.canonical_payload,report.dependency_manifest_hash,report.generation_reason,report.content_state,report.health_state,report.qa_status,report.qa_completed_at,report.publication_eligible,report.supersedes_report_id,report.superseded_by_report_id,report.created_by))

    def insert_dependency(self,cursor,dep: ReportDependency)->None:
        self._hash64(dep.semantic_fingerprint,'semantic_fingerprint')
        cursor.execute(self.INSERT_DEP,(dep.report_dependency_id,dep.report_id,dep.dependency_type,dep.dependency_id,dep.semantic_fingerprint,dep.dependency_version,dep.source_snapshot_id))

    def find_equivalent(self,cursor,property_id: UUID,report_variant: str,report_input_hash: str)->UUID|None:
        self._hash64(report_input_hash,'report_input_hash')
        cursor.execute(self.FIND_EQUIVALENT,(property_id,report_variant,report_input_hash)); row=cursor.fetchone()
        return UUID(str(row[0])) if row else None

    def insert_diff(self,cursor,report_diff_id,old_report_id,new_report_id,diff_payload,diff_hash):
        self._hash64(diff_hash,'diff_hash')
        cursor.execute(self.INSERT_DIFF,(report_diff_id,old_report_id,new_report_id,diff_payload,diff_hash))

    def mark_validating(self,cursor,report_id: UUID)->bool:
        cursor.execute(self.MARK_VALIDATING,(report_id,))
        return cursor.fetchone() is not None

    def mark_ready(self,cursor,report_id: UUID)->bool:
        cursor.execute(self.MARK_READY,(report_id,))
        return cursor.fetchone() is not None

