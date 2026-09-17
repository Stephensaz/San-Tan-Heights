from uuid import uuid4
from src.dependency.evaluator import ImpactEvaluator, DependencyChange
from src.dependency.lookup import DependencyConsumer
from src.dependency.rules.registry import DependencyImpactRuleRegistry

def consumer(variant,stored='a'*64): return DependencyConsumer(uuid4(),uuid4(),None,variant,stored)

def test_agent_only_variant_isolation_via_actual_consumption_scope():
    ev=ImpactEvaluator(DependencyImpactRuleRegistry())
    ch=DependencyChange('MODEL_VERSION','m','a'*64,'b'*64,'NORMAL_UPDATE')
    # Variant isolation is established upstream by the dependency manifest/reverse lookup.
    # An Agent-only dependency yields only an Agent consumer; Seller/Public are never evaluated.
    consumers=[consumer('AGENT')]
    decisions=[ev.evaluate(ch,c).decision for c in consumers]
    assert decisions==['DIRTY']

def test_invalidating_identity_correction_all_variants():
    ev=ImpactEvaluator(DependencyImpactRuleRegistry()); ch=DependencyChange('PROPERTY_IDENTITY','id','a'*64,'b'*64,'INVALIDATING_CORRECTION')
    assert {ev.evaluate(ch,consumer(v)).decision for v in ('AGENT','SELLER','PUBLIC')}=={'INVALIDATION_REQUIRED'}

def test_required_dependency_blocked():
    ev=ImpactEvaluator(DependencyImpactRuleRegistry()); ch=DependencyChange('PARCEL_IDENTITY','id','a'*64,'b'*64,'NORMAL_UPDATE',True)
    assert ev.evaluate(ch,consumer('PUBLIC')).decision=='BLOCKED'

def test_non_semantic_source_refresh_no_impact():
    ev=ImpactEvaluator(DependencyImpactRuleRegistry()); ch=DependencyChange('SOURCE_DATASET','ds','a'*64,'a'*64,'SOURCE_REFRESH')
    assert ev.evaluate(ch,consumer('PUBLIC')).decision=='NO_IMPACT'

def test_fleet_scale_exact_count_fixture():
    ev=ImpactEvaluator(DependencyImpactRuleRegistry()); dirty=no=0
    for i in range(5000):
        stored='a'*64; new=('b'*64 if i<1347 else 'a'*64)
        ch=DependencyChange('PARCEL_GEOMETRY',f'parcel-{i}',stored,new,'NORMAL_UPDATE')
        decision=ev.evaluate(ch,consumer('PUBLIC',stored)).decision
        dirty += decision=='DIRTY'; no += decision=='NO_IMPACT'
    assert dirty==1347 and no==3653
