from pathlib import Path
from src.release.policy import ReleasePolicyRegistry
ROOT=Path(__file__).resolve().parents[3]

def test_release_policy_registry_loads_governed_standard_policy():
    r=ReleasePolicyRegistry.from_repository(ROOT); p=r.get('STANDARD_FLEET')
    assert r.registry_id=='STH-RELEASE-POLICY-v1.0'
    assert p.version=='1.0.0'
    assert p.allowed_variants==frozenset({'AGENT','SELLER','PUBLIC'})
    assert p.membership_sort==('property_id','report_variant','channel')
    assert p.require_membership_freeze is True
