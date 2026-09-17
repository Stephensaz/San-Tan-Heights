from uuid import uuid4
import pytest
from src.snapshot.governed_state import GovernedStateValidator, GovernedStateValidationError, GovernedStateClient
H='a'*64

def valid(pid=None):
    return {'property_id':str(pid or uuid4()),'governed_state_version':'g1','source_read_token':'tok1','intelligence_schema_version':'i1','governance_schema_version':'gov1','model_version':'m1','property_identity_status':'RESOLVED','qa_status':'PASS','findings':[{'finding_id':'F1','finding_type':'PHASE','passport_id':'P1','passport_version':'1','canonical_value':'B-3','confidence_code':'VERIFIED','qa_status':'PASS','production_status':'PRODUCTION_READY','publication_scope':'ALL','approved_wording':{'agent':'B-3','seller':'B-3','public':'B-3'},'wording_versions':{'agent':'1','seller':'1','public':'1'},'semantic_fingerprint':H,'evidence_reference_set_hash':H}],'dependencies':[{'dependency_type':'PROPERTY_IDENTITY','dependency_id':'D1','semantic_fingerprint':H,'record_fingerprint':H,'dependency_version':'1','required':True,'variant_scope':['AGENT','SELLER','PUBLIC']}]}

def test_valid_state_parses():
    s=GovernedStateValidator().validate(valid()); assert s.property_identity_status=='RESOLVED' and len(s.findings)==1

def test_unknown_status_fails_closed():
    x=valid(); x['findings'][0]['production_status']='MAGIC'
    with pytest.raises(GovernedStateValidationError): GovernedStateValidator().validate(x)

def test_bad_passport_reference_fails():
    x=valid(); x['findings'][0]['passport_id']=''
    with pytest.raises(GovernedStateValidationError): GovernedStateValidator().validate(x)

def test_bad_fingerprint_fails():
    x=valid(); x['dependencies'][0]['semantic_fingerprint']='bad'
    with pytest.raises(GovernedStateValidationError): GovernedStateValidator().validate(x)

def test_client_rejects_wrong_property():
    asked=uuid4(); returned=uuid4()
    class P:
        def get_governed_property_state(self, property_id): return valid(returned)
    with pytest.raises(ValueError): GovernedStateClient(P()).get(asked)
