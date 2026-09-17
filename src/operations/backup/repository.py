from __future__ import annotations
from .models import BackupVerificationRequest

class BackupVerificationRepository:
    INSERT='''INSERT INTO operations.backup_verifications
(verification_id,backup_id,backup_type,source_environment,expected_sha256,observed_sha256,expected_size_bytes,observed_size_bytes,manifest_fingerprint,verification_status,reason_codes,verifier_version,verified_by)
VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s)
ON CONFLICT(backup_id,observed_sha256,manifest_fingerprint) DO NOTHING RETURNING verification_id'''
    GET='''SELECT verification_id,verification_status,reason_codes FROM operations.backup_verifications
WHERE backup_id=%s AND observed_sha256=%s AND manifest_fingerprint=%s'''
    def record(self,cursor,request:BackupVerificationRequest,status:str,reason_codes:tuple[str,...]):
        import json
        cursor.execute(self.INSERT,(request.verification_id,request.backup_id,request.backup_type,request.source_environment,request.expected_sha256,request.observed_sha256,request.expected_size_bytes,request.observed_size_bytes,request.manifest_fingerprint,status,json.dumps(list(reason_codes)),request.verifier_version,request.verified_by))
        return cursor.fetchone()
