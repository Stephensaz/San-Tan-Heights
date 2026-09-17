from uuid import uuid4
from src.snapshot.governed_state.models import GovernedPropertyState, GovernedFinding, GovernedDependency

FP="a"*64
EF="b"*64

def state(*, identity="RESOLVED", qa="PASS", findings=(), dependencies=()):
    return GovernedPropertyState(uuid4(),"gs-1","token-1","intel-1","gov-1","model-1",identity,qa,tuple(findings),tuple(dependencies))

def finding(fid="f1", ftype="REAR_ADJACENCY", status="PRODUCTION_READY", qa="PASS", value=None):
    return GovernedFinding(fid,ftype,"p1","v1",value if value is not None else {"code":"COMMON_AREA"},"VERIFIED",qa,status,"ALL",
        {"agent":"Agent text","seller":"Seller text","public":"Public text"},{"agent":"1","seller":"1","public":"1"},FP,EF)

def dep(dtype="PROPERTY_IDENTITY", did="d1"):
    return GovernedDependency(dtype,did,FP,EF,"1",True,("AGENT","SELLER","PUBLIC"))
