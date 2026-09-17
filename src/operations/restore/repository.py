from __future__ import annotations
from .models import RestoreVerificationRequest,GlobalPublicationFreeze

class RestoreVerificationRepository:
    BACKUP_STATUS='''SELECT verification_status FROM operations.backup_verifications WHERE verification_id=%s'''
    INSERT='''INSERT INTO operations.restore_verifications
(restore_verification_id,backup_verification_id,restored_environment,schema_version,expected_manifest_fingerprint,observed_manifest_fingerprint,integrity_check_status,row_count_check_status,verification_status,reason_codes,verifier_version,verified_by)
VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s)
ON CONFLICT(restore_verification_id) DO NOTHING RETURNING restore_verification_id'''
    def backup_status(self,cursor,backup_verification_id):
        cursor.execute(self.BACKUP_STATUS,(backup_verification_id,)); row=cursor.fetchone(); return None if not row else row[0]
    def record(self,cursor,request:RestoreVerificationRequest,status:str,reasons:tuple[str,...]):
        import json
        cursor.execute(self.INSERT,(request.restore_verification_id,request.backup_verification_id,request.restored_environment,request.schema_version,request.expected_manifest_fingerprint,request.observed_manifest_fingerprint,request.integrity_check_status,request.row_count_check_status,status,json.dumps(list(reasons)),request.verifier_version,request.verified_by)); return cursor.fetchone()

class GlobalPublicationFreezeRepository:
    INSERT='''INSERT INTO operations.global_publication_freezes(freeze_id,reason_code,restore_verification_id,created_by)
VALUES (%s,%s,%s,%s) ON CONFLICT DO NOTHING'''
    ACTIVE='''SELECT freeze_id,reason_code FROM operations.global_publication_freezes WHERE released_at IS NULL ORDER BY created_at DESC LIMIT 1'''
    RELEASE='''UPDATE operations.global_publication_freezes SET released_at=now(),released_by=%s WHERE freeze_id=%s AND released_at IS NULL RETURNING freeze_id'''
    def create(self,cursor,freeze:GlobalPublicationFreeze): cursor.execute(self.INSERT,(freeze.freeze_id,freeze.reason_code,freeze.restore_verification_id,freeze.created_by))
    def active(self,cursor,*_args):
        cursor.execute(self.ACTIVE); row=cursor.fetchone(); return None if not row else (row[0],row[1])
    def release(self,cursor,freeze_id,actor): cursor.execute(self.RELEASE,(actor,freeze_id)); return cursor.fetchone() is not None
