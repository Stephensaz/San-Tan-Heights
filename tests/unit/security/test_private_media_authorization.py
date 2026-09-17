from pathlib import Path
import pytest
from src.security.authorization import HumanRoleRegistry, HumanPrincipal, AuthorizationPolicyEngine, PropertyScopedAuthorization, AuthorizationDenied
from src.security.media import PrivateMediaAuthorization, PrivateMediaResource
ROOT=Path(__file__).resolve().parents[3]

def service():
    r=HumanRoleRegistry.from_repository(ROOT); p=AuthorizationPolicyEngine(r)
    assignments={('seller','p1'),('agent','p1')}
    return PrivateMediaAuthorization(p,PropertyScopedAuthorization(r,lambda s,prop:(s,prop) in assignments))

def test_seller_can_read_assigned_seller_media_but_not_agent_media():
    s=service(); principal=HumanPrincipal('seller','SELLER')
    assert s.require(principal,PrivateMediaResource('m1','p1','SELLER')).allowed
    with pytest.raises(AuthorizationDenied): s.require(principal,PrivateMediaResource('m2','p1','AGENT'))

def test_agent_requires_property_assignment_and_cleared_approved_media():
    s=service(); principal=HumanPrincipal('agent','AGENT')
    assert s.require(principal,PrivateMediaResource('m1','p1','AGENT')).allowed
    with pytest.raises(AuthorizationDenied): s.require(principal,PrivateMediaResource('m2','p2','AGENT'))
    with pytest.raises(AuthorizationDenied): s.require(principal,PrivateMediaResource('m3','p1','AGENT',approval_status='PENDING'))
    with pytest.raises(AuthorizationDenied): s.require(principal,PrivateMediaResource('m4','p1','AGENT',rights_status='UNCLEARED'))

def test_operations_cannot_read_restricted_media_but_admin_can():
    s=service()
    with pytest.raises(AuthorizationDenied): s.require(HumanPrincipal('ops','OPERATIONS'),PrivateMediaResource('m','p9','RESTRICTED'))
    assert s.require(HumanPrincipal('admin','ADMIN'),PrivateMediaResource('m','p9','RESTRICTED')).allowed
