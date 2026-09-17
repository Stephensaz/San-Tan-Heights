from __future__ import annotations
import re
from .models import BackupVerificationRequest, BackupVerificationResult

_SHA=re.compile(r'^[0-9a-f]{64}$')
class BackupVerifier:
    """Fail-closed verification of backup integrity metadata before restore eligibility."""
    def __init__(self,repository=None): self.repository=repository
    def verify(self,cursor,request:BackupVerificationRequest)->BackupVerificationResult:
        reasons=[]
        if request.backup_type not in {'FULL','LOGICAL','PHYSICAL'}: reasons.append('BACKUP_TYPE_UNSUPPORTED')
        if not _SHA.match(request.expected_sha256 or '') or not _SHA.match(request.observed_sha256 or ''): reasons.append('BACKUP_HASH_INVALID')
        elif request.expected_sha256 != request.observed_sha256: reasons.append('BACKUP_HASH_MISMATCH')
        if request.expected_size_bytes <= 0 or request.observed_size_bytes <= 0: reasons.append('BACKUP_SIZE_INVALID')
        elif request.expected_size_bytes != request.observed_size_bytes: reasons.append('BACKUP_SIZE_MISMATCH')
        if not _SHA.match(request.manifest_fingerprint or ''): reasons.append('BACKUP_MANIFEST_FINGERPRINT_INVALID')
        status='FAILED' if reasons else 'VERIFIED'
        result=BackupVerificationResult(status,tuple(reasons))
        if self.repository is not None:self.repository.record(cursor,request,status,result.reason_codes)
        return result
