from __future__ import annotations
from uuid import uuid4
from .models import RestoreVerificationRequest,RestoreVerificationResult,GlobalPublicationFreeze

class RestoreVerifier:
    def __init__(self,repository): self.repository=repository
    def verify(self,cursor,request:RestoreVerificationRequest)->RestoreVerificationResult:
        reasons=[]
        if self.repository.backup_status(cursor,request.backup_verification_id)!='VERIFIED': reasons.append('RESTORE_SOURCE_BACKUP_NOT_VERIFIED')
        if request.expected_manifest_fingerprint != request.observed_manifest_fingerprint: reasons.append('RESTORE_MANIFEST_MISMATCH')
        if request.integrity_check_status!='PASS': reasons.append('RESTORE_INTEGRITY_CHECK_FAILED')
        if request.row_count_check_status!='PASS': reasons.append('RESTORE_ROW_COUNT_CHECK_FAILED')
        if not request.schema_version: reasons.append('RESTORE_SCHEMA_VERSION_MISSING')
        status='FAILED' if reasons else 'VERIFIED'; result=RestoreVerificationResult(status,tuple(reasons))
        self.repository.record(cursor,request,status,result.reason_codes); return result

class PostRestoreFreezeService:
    """A successful production restore must create a global publication freeze."""
    def __init__(self,freeze_repository): self.freeze_repository=freeze_repository
    def apply(self,cursor,*,restore_verification_id,restore_status,actor='RESTORE_SERVICE'):
        if restore_status!='VERIFIED': return None
        active=self.freeze_repository.active(cursor)
        if active:return active[0]
        freeze=GlobalPublicationFreeze(uuid4(),'POST_RESTORE_PUBLICATION_FREEZE',restore_verification_id,actor)
        self.freeze_repository.create(cursor,freeze); return freeze.freeze_id
