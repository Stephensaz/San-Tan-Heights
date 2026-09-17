from pathlib import Path
from uuid import uuid4
from src.operations.containment.registry import ContainmentRuleRegistry
from src.operations.containment.service import AutomaticContainment
from src.operations.incidents.models import Incident
ROOT=Path(__file__).resolve().parents[3]
class C:
    def __init__(self):self.sql=[]
    def execute(self,q,p=()):self.sql.append((q,p))
class FreezeRepo:
    def __init__(self):self.created=[]
    def create(self,cursor,freeze):self.created.append(freeze)

def test_pointer_incident_is_contained_by_publication_freeze():
    reg=ContainmentRuleRegistry.from_repository(ROOT); fr=FreezeRepo(); svc=AutomaticContainment(reg,freeze_repository=fr); c=C()
    i=Incident(uuid4(),'k','PUBLICATION_POINTER_INTEGRITY','ERROR','OPEN','INCIDENT_DETECTED',property_id=uuid4(),report_variant='PUBLIC',channel='WEB')
    r=svc.contain(c,incident=i,target_key='p:PUBLIC:WEB')
    assert r.status=='APPLIED' and r.action_type=='FREEZE_PUBLICATION_TARGET'
    assert len(fr.created)==1 and fr.created[0].channel=='WEB'

def test_low_severity_does_not_contain_error_rule():
    reg=ContainmentRuleRegistry.from_repository(ROOT); svc=AutomaticContainment(reg); i=Incident(uuid4(),'k','PUBLICATION_POINTER_INTEGRITY','WARNING','OPEN','INCIDENT_DETECTED')
    assert svc.contain(C(),incident=i,target_key='x').status=='NO_ACTION'
