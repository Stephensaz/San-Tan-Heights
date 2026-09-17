from __future__ import annotations
import json
from .models import SnapshotRecord, SnapshotFindingRecord, SnapshotDependencyRecord, SnapshotRequirementResultRecord, SnapshotDiffRecord

class SnapshotRepository:
    FIND_EQUIVALENT='''SELECT snapshot_id FROM snapshot.intelligence_snapshots WHERE property_id=%s AND semantic_fingerprint=%s AND qa_status='PASS' AND snapshot_completeness_status IN ('COMPLETE','PARTIAL_VALID') ORDER BY snapshot_sequence DESC LIMIT 1'''
    CURRENT_ACCEPTED='''SELECT snapshot_id FROM snapshot.intelligence_snapshots WHERE property_id=%s AND qa_status='PASS' AND snapshot_completeness_status IN ('COMPLETE','PARTIAL_VALID') ORDER BY snapshot_sequence DESC LIMIT 1'''
    ALLOCATE_COUNTER='''INSERT INTO snapshot.snapshot_sequence_counters(property_id,next_sequence) VALUES (%s,2) ON CONFLICT(property_id) DO UPDATE SET next_sequence=snapshot.snapshot_sequence_counters.next_sequence+1, updated_at=now() RETURNING next_sequence-1'''
    INSERT='''INSERT INTO snapshot.intelligence_snapshots
    (snapshot_id,property_id,snapshot_sequence,snapshot_reason,governed_state_version,source_read_token,intelligence_schema_version,governance_schema_version,model_version,semantic_fingerprint,agent_semantic_fingerprint,seller_semantic_fingerprint,public_semantic_fingerprint,snapshot_hash,snapshot_completeness_status,qa_status,qa_completed_at,supersedes_snapshot_id,created_by)
    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)'''
    def find_equivalent(self,cursor,property_id,semantic_fingerprint):
        cursor.execute(self.FIND_EQUIVALENT,(property_id,semantic_fingerprint)); row=cursor.fetchone(); return None if row is None else __import__('uuid').UUID(str(row[0]))
    def current_accepted(self,cursor,property_id):
        cursor.execute(self.CURRENT_ACCEPTED,(property_id,)); row=cursor.fetchone(); return None if row is None else __import__('uuid').UUID(str(row[0]))
    def allocate_sequence(self,cursor,property_id):
        cursor.execute(self.ALLOCATE_COUNTER,(property_id,)); row=cursor.fetchone(); return int(row[0])
    def insert(self,cursor,r:SnapshotRecord): cursor.execute(self.INSERT,(r.snapshot_id,r.property_id,r.snapshot_sequence,r.snapshot_reason,r.governed_state_version,r.source_read_token,r.intelligence_schema_version,r.governance_schema_version,r.model_version,r.semantic_fingerprint,r.agent_semantic_fingerprint,r.seller_semantic_fingerprint,r.public_semantic_fingerprint,r.snapshot_hash,r.snapshot_completeness_status,r.qa_status,r.qa_completed_at,r.supersedes_snapshot_id,r.created_by))

class SnapshotFindingRepository:
    INSERT='''INSERT INTO snapshot.snapshot_findings (snapshot_finding_id,snapshot_id,finding_id,finding_type,passport_id,passport_version,passport_semantic_fingerprint,canonical_value,confidence_code,qa_status,production_status,publication_scope,agent_wording,seller_wording,public_wording,agent_wording_version,seller_wording_version,public_wording_version,semantic_fingerprint,evidence_reference_set_hash) VALUES (%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)'''
    def insert(self,cursor,r:SnapshotFindingRecord): cursor.execute(self.INSERT,(r.snapshot_finding_id,r.snapshot_id,r.finding_id,r.finding_type,r.passport_id,r.passport_version,r.passport_semantic_fingerprint,json.dumps(r.canonical_value,separators=(',',':'),sort_keys=True),r.confidence_code,r.qa_status,r.production_status,r.publication_scope,r.agent_wording,r.seller_wording,r.public_wording,r.agent_wording_version,r.seller_wording_version,r.public_wording_version,r.semantic_fingerprint,r.evidence_reference_set_hash))

class SnapshotDependencyRepository:
    INSERT='''INSERT INTO snapshot.snapshot_dependencies (snapshot_dependency_id,snapshot_id,dependency_type,dependency_id,record_fingerprint,semantic_fingerprint,dependency_version,required,affects_agent,affects_seller,affects_public) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)'''
    def insert(self,cursor,r:SnapshotDependencyRecord): cursor.execute(self.INSERT,(r.snapshot_dependency_id,r.snapshot_id,r.dependency_type,r.dependency_id,r.record_fingerprint,r.semantic_fingerprint,r.dependency_version,r.required,r.affects_agent,r.affects_seller,r.affects_public))

class SnapshotRequirementRepository:
    INSERT='''INSERT INTO snapshot.snapshot_requirement_results (snapshot_requirement_result_id,snapshot_id,requirement_id,requirement_scope,required_flag,status,finding_id,dependency_type,dependency_id,reason_code) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)'''
    def insert(self,cursor,r:SnapshotRequirementResultRecord): cursor.execute(self.INSERT,(r.snapshot_requirement_result_id,r.snapshot_id,r.requirement_id,r.requirement_scope,r.required_flag,r.status,r.finding_id,r.dependency_type,r.dependency_id,r.reason_code))

class SnapshotDiffRepository:
    INSERT='''INSERT INTO snapshot.snapshot_diffs (snapshot_diff_id,old_snapshot_id,new_snapshot_id,diff_payload,diff_hash) VALUES (%s,%s,%s,%s::jsonb,%s)'''
    def insert(self,cursor,r:SnapshotDiffRecord): cursor.execute(self.INSERT,(r.snapshot_diff_id,r.old_snapshot_id,r.new_snapshot_id,json.dumps(r.diff_payload,separators=(',',':'),sort_keys=True),r.diff_hash))
