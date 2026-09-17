from uuid import uuid4
from src.dependency.batch.models import DependencyChangeItem
from src.dependency.batch.evaluator import BulkImpactEvaluator
from src.dependency.lookup import DependencyConsumer
from src.dependency.rules.registry import DependencyImpactRuleRegistry
from src.dependency.evaluator import ImpactEvaluator

class Repo:
    def __init__(self,items): self.items=items; self.done=[]; self.failed=[]
    def claim_items(self,cursor,batch_id,limit): return self.items[:limit]
    def complete_item(self,cursor,item_id,summary): self.done.append((item_id,summary))
    def fail_item(self,cursor,item_id,error): self.failed.append((item_id,error))
class Lookup:
    def __init__(self,by_property): self.by_property=by_property
    def lookup(self,cursor,t,d): return tuple(self.by_property.values())

def item(pid,old='a'*64,new='b'*64,blocked=False,change='NORMAL_UPDATE'):
    return DependencyChangeItem(uuid4(),uuid4(),pid,'rear',change,old,new,blocked)

def test_bulk_exact_affected_and_unaffected_counts():
    p1,p2=uuid4(),uuid4(); i1,i2=item(p1),item(p2,new='a'*64)
    consumers={p1:DependencyConsumer(p1,uuid4(),None,'PUBLIC','a'*64),p2:DependencyConsumer(p2,uuid4(),None,'PUBLIC','a'*64)}
    r=Repo([i1,i2]); ev=BulkImpactEvaluator(r,Lookup(consumers),ImpactEvaluator(DependencyImpactRuleRegistry()))
    out=ev.evaluate_claimed(None,batch_id=i1.batch_id,dependency_type='REAR_ADJACENCY',correlation_id=uuid4())
    assert out.decision_counts=={'DIRTY':1,'NO_IMPACT':1}; assert out.affected_items==1; assert len(r.done)==2; assert not r.failed

def test_no_consumers_is_no_impact():
    p=uuid4(); i=item(p); r=Repo([i]); out=BulkImpactEvaluator(r,Lookup({})).evaluate_claimed(None,batch_id=i.batch_id,dependency_type='REAR_ADJACENCY',correlation_id=uuid4())
    assert out.decision_counts=={'NO_IMPACT':1}
