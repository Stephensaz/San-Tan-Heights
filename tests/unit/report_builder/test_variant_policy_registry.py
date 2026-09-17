from pathlib import Path
import pytest
from src.report_builder.variant import VariantPolicyRegistry, VariantPolicyRegistryError

ROOT=Path(__file__).resolve().parents[3]

def test_all_three_variant_policies_load():
    r=VariantPolicyRegistry.from_repository(ROOT)
    assert r.variants == ('AGENT','SELLER','PUBLIC')

def test_public_is_strictest_classification_policy():
    r=VariantPolicyRegistry.from_repository(ROOT)
    assert r.get('PUBLIC').allowed_classifications == frozenset({'PUBLIC_DATA'})
    assert 'AGENT_INTERNAL' in r.get('AGENT').allowed_classifications
    assert 'AGENT_INTERNAL' not in r.get('SELLER').allowed_classifications

def test_publication_scope_is_audience_safe():
    r=VariantPolicyRegistry.from_repository(ROOT)
    assert r.get('PUBLIC').allows_publication_scope('PUBLIC')
    assert not r.get('PUBLIC').allows_publication_scope('AGENT')
    assert r.get('SELLER').allows_publication_scope('AGENT_SELLER')

def test_unknown_variant_fails_closed():
    r=VariantPolicyRegistry.from_repository(ROOT)
    with pytest.raises(VariantPolicyRegistryError): r.get('OPS')
