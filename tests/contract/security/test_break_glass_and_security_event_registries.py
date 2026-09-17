from pathlib import Path
from src.security.break_glass import BreakGlassPolicyRegistry
from src.security.audit import SecurityEventRegistry
ROOT=Path(__file__).resolve().parents[3]
def test_break_glass_policy_locked_and_bounded():
    r=BreakGlassPolicyRegistry.from_repository(ROOT); assert r.max_duration_minutes==60; assert 'security.break_glass.delegate' in r.prohibited_actions
def test_security_event_taxonomy_contains_critical_controls():
    r=SecurityEventRegistry.from_repository(ROOT)
    for e in ['BREAK_GLASS_ISSUED','BREAK_GLASS_USED','SECURITY_POLICY_MUTATION_DETECTED']: assert r.require(e)
