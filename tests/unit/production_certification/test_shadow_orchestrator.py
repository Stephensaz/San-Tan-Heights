from uuid import uuid4
import pytest
from src.production_certification.shadow.orchestrator import ShadowModeOrchestrator
H='a'*64
class Exec:
    def __init__(self): self.generated=[]; self.compared=[]
    def generate(self,*,property_id,variant): self.generated.append((property_id,variant)); return {'property_id':str(property_id),'variant':variant,'value':'shadow'}
    def compare_current(self,*,property_id,variant,generated): self.compared.append((property_id,variant)); return {'same_semantics':variant!='PUBLIC'}
class BadExec(Exec):
    def generate(self,**kw): raise RuntimeError('boom')

def test_shadow_orchestrator_runs_without_publication_capability():
    e=Exec(); ids=[uuid4(),uuid4()]
    r=ShadowModeOrchestrator().run(production_certification_id=uuid4(),policy_version='1',selected_property_ids=ids,membership_fingerprint=H,variants=('PUBLIC','AGENT'),executor=e)
    assert r.status=='PASS' and len(r.target_results)==4
    assert not hasattr(e,'publish')
    assert len(r.evidence_hash)==64

def test_shadow_orchestrator_rejects_publication_mutation_flag():
    with pytest.raises(ValueError,match='cannot allow publication mutation'):
        ShadowModeOrchestrator().run(production_certification_id=uuid4(),policy_version='1',selected_property_ids=[uuid4()],membership_fingerprint=H,variants=('PUBLIC',),executor=Exec(),publication_mutation_allowed=True)

def test_shadow_orchestrator_fail_closes_target_error_without_activation():
    r=ShadowModeOrchestrator().run(production_certification_id=uuid4(),policy_version='1',selected_property_ids=[uuid4()],membership_fingerprint=H,variants=('PUBLIC',),executor=BadExec())
    assert r.status=='FAIL' and r.target_results[0].status=='FAIL'
