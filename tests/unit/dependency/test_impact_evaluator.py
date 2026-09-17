from uuid import uuid4
from src.dependency.evaluator import DependencyChange, ImpactEvaluator
from src.dependency.lookup import DependencyConsumer

def consumer(variant='PUBLIC', fp='a'*64): return DependencyConsumer(uuid4(),uuid4(),None,variant,fp)

def test_unchanged_semantics_are_no_impact():
    d=ImpactEvaluator().evaluate(DependencyChange('REAR_ADJACENCY','r','a'*64,'a'*64,'SOURCE_REFRESH'),consumer())
    assert d.decision=='NO_IMPACT' and d.reason_code=='DEPENDENCY_SEMANTICS_UNCHANGED'

def test_normal_semantic_change_is_dirty():
    d=ImpactEvaluator().evaluate(DependencyChange('REAR_ADJACENCY','r','a'*64,'b'*64,'NORMAL_UPDATE'),consumer())
    assert d.decision=='DIRTY'

def test_invalidating_correction_escalates():
    d=ImpactEvaluator().evaluate(DependencyChange('PROPERTY_IDENTITY','id','a'*64,'b'*64,'INVALIDATING_CORRECTION'),consumer())
    assert d.decision=='INVALIDATION_REQUIRED'

def test_required_dependency_blocked():
    d=ImpactEvaluator().evaluate(DependencyChange('PARCEL_IDENTITY','id','a'*64,None,'CORRECTION',required_state_blocked=True),consumer())
    assert d.decision=='BLOCKED'
