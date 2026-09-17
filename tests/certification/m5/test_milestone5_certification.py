from uuid import uuid4
from src.operations.backup import BackupVerifier,BackupVerificationRequest
from src.operations.restore import RestoreVerifier,RestoreVerificationRequest,PostRestoreFreezeService
from src.operations.health.property_health import PropertyHealthModel
from src.operations.health.fleet_health import FleetHealthModel
class BR:
    def record(self,*a):pass
class RR:
    def backup_status(self,*a):return 'VERIFIED'
    def record(self,*a):pass
class FR:
    def __init__(self):self.created=[]
    def active(self,*a):return None
    def create(self,c,x):self.created.append(x)
def test_m5_backup_restore_freeze_and_health_chain():
    b=BackupVerificationRequest(uuid4(),'b','FULL','prod','a'*64,'a'*64,1,1,'b'*64,'1','ops')
    assert BackupVerifier(BR()).verify(object(),b).status=='VERIFIED'
    rid=uuid4(); r=RestoreVerificationRequest(rid,b.verification_id,'restore','1','b'*64,'b'*64,'PASS','PASS','1','ops')
    assert RestoreVerifier(RR()).verify(object(),r).status=='VERIFIED'
    f=FR(); assert PostRestoreFreezeService(f).apply(object(),restore_verification_id=rid,restore_status='VERIFIED')
    p=PropertyHealthModel().evaluate(property_id=uuid4(),has_current_snapshot=True)
    assert FleetHealthModel().aggregate([p]).status=='HEALTHY'
