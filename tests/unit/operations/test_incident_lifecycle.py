from uuid import uuid4
import pytest
from src.operations.incidents.models import Incident
from src.operations.incidents.service import IncidentLifecycle

class C:
    rowcount=1
    def __init__(self):self.sql=[]
    def execute(self,q,p=()):self.sql.append((q,p))

def incident(state='OPEN'):
    return Incident(uuid4(),'pointer:x','PUBLICATION_POINTER_INTEGRITY','ERROR',state,'INCIDENT_DETECTED',property_id=uuid4(),report_variant='PUBLIC',channel='WEB')

def test_incident_lifecycle_records_transition_without_rewriting_identity():
    c=C(); i=incident(); r=IncidentLifecycle().transition(c,incident=i,to_state='CONTAINED',reason_code='INCIDENT_AUTOMATIC_CONTAINMENT')
    assert r.status=='TRANSITIONED' and r.to_state=='CONTAINED'
    assert any('incident_history' in q for q,_ in c.sql)

def test_closed_incident_cannot_be_reopened():
    with pytest.raises(ValueError): IncidentLifecycle().transition(C(),incident=incident('CLOSED'),to_state='OPEN',reason_code='INCIDENT_DETECTED')
