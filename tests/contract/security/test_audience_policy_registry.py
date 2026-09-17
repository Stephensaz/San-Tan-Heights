from pathlib import Path
from src.security.audience import AudiencePolicyRegistry

ROOT=Path(__file__).resolve().parents[3]

def test_audience_registry_is_locked_and_complete():
    r=AudiencePolicyRegistry(ROOT/'registries/security/audience-policy-v1.0.yaml')
    assert r.registry_id=='STH-AUDIENCE-POLICY-v1.0'
    assert r.get('PUBLIC').report_variants==frozenset({'PUBLIC'})
    assert r.get('SELLER').report_variants==frozenset({'PUBLIC','SELLER'})
    assert r.get('AGENT').report_variants==frozenset({'PUBLIC','SELLER','AGENT'})
