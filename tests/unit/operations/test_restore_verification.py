from uuid import uuid4
from src.operations.restore import RestoreVerifier,RestoreVerificationRequest,PostRestoreFreezeService
class Repo:
    def __init__(self,status='VERIFIED'):self.status=status;self.records=[]
    def backup_status(self,c,i):return self.status
    def record(self,c,r,s,reasons):self.records.append((s,reasons))
def req(**kw):
    d=dict(restore_verification_id=uuid4(),backup_verification_id=uuid4(),restored_environment='restore-test',schema_version='0.1.32',expected_manifest_fingerprint='a'*64,observed_manifest_fingerprint='a'*64,integrity_check_status='PASS',row_count_check_status='PASS',verifier_version='1',verified_by='ops');d.update(kw);return RestoreVerificationRequest(**d)
def test_restore_requires_verified_backup_and_exact_integrity():
    x=RestoreVerifier(Repo()).verify(object(),req()); assert x.status=='VERIFIED'
def test_restore_from_unverified_backup_fails():
    x=RestoreVerifier(Repo('FAILED')).verify(object(),req()); assert x.status=='FAILED' and 'RESTORE_SOURCE_BACKUP_NOT_VERIFIED' in x.reason_codes
class F:
    def __init__(self):self.created=[]
    def active(self,c):return None
    def create(self,c,x):self.created.append(x)
def test_verified_restore_forces_global_publication_freeze():
    f=F(); fid=PostRestoreFreezeService(f).apply(object(),restore_verification_id=uuid4(),restore_status='VERIFIED'); assert fid and f.created[0].reason_code=='POST_RESTORE_PUBLICATION_FREEZE'
def test_failed_restore_does_not_create_freeze():
    f=F(); assert PostRestoreFreezeService(f).apply(object(),restore_verification_id=uuid4(),restore_status='FAILED') is None and not f.created
