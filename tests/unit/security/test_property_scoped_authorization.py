from pathlib import Path
import pytest
from src.security.authorization import HumanRoleRegistry, HumanPrincipal, AuthorizationPolicyEngine, PropertyScopedAuthorization, AuthorizationDenied
ROOT=Path(__file__).resolve().parents[3]

def setup():
    r=HumanRoleRegistry.from_repository(ROOT); e=AuthorizationPolicyEngine(r)
    assignments={('seller-1','p1'),('agent-1','p1')}
    return r,e,PropertyScopedAuthorization(r,lambda subject,prop:(subject,prop) in assignments)

def test_assigned_seller_and_agent_are_limited_to_assigned_property():
    r,e,s=setup()
    for principal in [HumanPrincipal('seller-1','SELLER'),HumanPrincipal('agent-1','AGENT')]:
        d=e.require(principal,action='property.current_report.read',classification='PUBLIC_DATA')
        s.require(principal,d,property_id='p1')
        with pytest.raises(AuthorizationDenied): s.require(principal,d,property_id='p2')

def test_fleet_scoped_operations_can_access_any_property_but_missing_property_still_fails():
    r,e,s=setup(); p=HumanPrincipal('ops-1','OPERATIONS')
    d=e.require(p,action='property.current_report.read',classification='AGENT_INTERNAL')
    s.require(p,d,property_id='p999')
    with pytest.raises(AuthorizationDenied): s.require(p,d,property_id=None)

def test_unprotected_public_action_does_not_require_assignment():
    r,e,s=setup(); p=HumanPrincipal('anon','PUBLIC')
    d=e.require(p,action='publication.current_public.read',classification='PUBLIC_DATA')
    s.require(p,d,property_id=None)
