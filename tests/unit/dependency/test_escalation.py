from uuid import uuid4
from src.dependency.escalation import DependencyImpactEscalationService
from src.dependency.evaluator import ImpactDecision
class Reviews:
    def __init__(self): self.calls=0
    def create(self,*a,**k): self.calls+=1; return uuid4()
def d(decision): return ImpactDecision(uuid4(),None,'PUBLIC','PROPERTY_IDENTITY','x','a'*64,'b'*64,'INVALIDATING_CORRECTION',decision,'r','INVALIDATING_CORRECTION')
def test_invalidation_is_recommendation_only():
    r=Reviews(); out=DependencyImpactEscalationService(r).escalate(None,decision=d('INVALIDATION_REQUIRED'),source_event_id=uuid4(),correlation_id=uuid4())
    assert out['action']=='INVALIDATION_RECOMMENDED'; assert r.calls==0
def test_block_does_not_unpublish():
    out=DependencyImpactEscalationService(Reviews()).escalate(None,decision=d('BLOCKED'),source_event_id=uuid4(),correlation_id=uuid4())
    assert out=={'action':'BLOCKED_DOWNSTREAM'}
def test_review_required_creates_review_item():
    r=Reviews(); out=DependencyImpactEscalationService(r).escalate(None,decision=d('REVIEW_REQUIRED'),source_event_id=uuid4(),correlation_id=uuid4())
    assert out['action']=='REVIEW_ITEM_CREATED'; assert r.calls==1
