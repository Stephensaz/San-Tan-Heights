from pathlib import Path
from src.regeneration.priority import PriorityRegistry, PriorityResolver
ROOT=Path(__file__).resolve().parents[3]

def test_priority_registry_loads_exact_classes():
    r=PriorityRegistry.from_repository(ROOT)
    assert r.classes=={'CRITICAL':100,'HIGH':80,'NORMAL':50,'BULK':30,'LOW':10}

def test_invalidating_correction_is_critical():
    p=PriorityResolver(PriorityRegistry.from_repository(ROOT)).resolve(trigger_type='REPORT_MARKED_DIRTY',change_class='INVALIDATING_CORRECTION')
    assert (p.priority_class,p.priority_score)==('CRITICAL',100)

def test_bulk_release_is_bulk_and_default_is_normal():
    resolver=PriorityResolver(PriorityRegistry.from_repository(ROOT))
    assert resolver.resolve(trigger_type='RELEASE_REGENERATION_REQUESTED').priority_class=='BULK'
    assert resolver.resolve(trigger_type='REPORT_MARKED_DIRTY',change_class='NORMAL_UPDATE').priority_class=='NORMAL'
