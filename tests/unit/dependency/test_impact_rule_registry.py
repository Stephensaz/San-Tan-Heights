from pathlib import Path
import yaml
import pytest
from src.dependency.rules import DependencyImpactRuleRegistry, DependencyImpactRuleError
ROOT=Path(__file__).resolve().parents[3]

def test_registry_covers_all_production_dependency_types():
    registry=DependencyImpactRuleRegistry()
    types=set(yaml.safe_load((ROOT/'registries/dependency-types.yaml').read_text())['types'])-{'TEST_DEP'}
    assert {r.dependency_type for r in registry.rules}==types
    assert registry.get('PROPERTY_IDENTITY').invalidating_change=='INVALIDATION_REQUIRED'

def test_unknown_rule_fails_closed():
    with pytest.raises(DependencyImpactRuleError):
        DependencyImpactRuleRegistry().get('NOPE')
