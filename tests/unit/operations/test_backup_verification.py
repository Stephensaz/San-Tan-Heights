from uuid import uuid4
from src.operations.backup import BackupVerifier,BackupVerificationRequest
class R:
    def __init__(self):self.calls=[]
    def record(self,c,r,s,reasons):self.calls.append((r,s,reasons))
def req(**kw):
    d=dict(verification_id=uuid4(),backup_id='b1',backup_type='FULL',source_environment='prod',expected_sha256='a'*64,observed_sha256='a'*64,expected_size_bytes=10,observed_size_bytes=10,manifest_fingerprint='b'*64,verifier_version='1',verified_by='ops');d.update(kw);return BackupVerificationRequest(**d)
def test_backup_verifies_exact_hash_size_and_manifest_shape():
    r=R(); result=BackupVerifier(r).verify(object(),req()); assert result.status=='VERIFIED' and not result.reason_codes and r.calls
def test_backup_hash_mismatch_fails_closed():
    result=BackupVerifier().verify(object(),req(observed_sha256='c'*64)); assert result.status=='FAILED' and 'BACKUP_HASH_MISMATCH' in result.reason_codes
