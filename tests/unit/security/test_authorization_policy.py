from pathlib import Path
import pytest
from src.security.authorization import HumanRoleRegistry, HumanPrincipal, AuthorizationPolicyEngine, AuthorizationDenied
ROOT=Path(__file__).resolve().parents[3]

def engine(): return AuthorizationPolicyEngine(HumanRoleRegistry.from_repository(ROOT))

def test_agent_can_read_agent_internal_but_cannot_manage_publication_or_restricted_data():
    p=HumanPrincipal('u1','AGENT'); e=engine()
    assert e.require(p,action='property.intelligence.read',classification='AGENT_INTERNAL').allowed
    assert e.evaluate(p,action='publication.manage',classification='PUBLIC_DATA').reason=='ACTION_DENIED'
    assert e.evaluate(p,action='property.current_report.read',classification='RESTRICTED').reason=='CLASSIFICATION_DENIED'

def test_public_cannot_cross_into_protected_property_action():
    d=engine().evaluate(HumanPrincipal('anon','PUBLIC'),action='property.current_report.read',classification='PUBLIC_DATA')
    assert not d.allowed and d.reason=='ACTION_DENIED'

def test_unknown_action_fails_closed():
    with pytest.raises(AuthorizationDenied): engine().require(HumanPrincipal('u1','ADMIN'),action='does.not.exist',classification='PUBLIC_DATA')
