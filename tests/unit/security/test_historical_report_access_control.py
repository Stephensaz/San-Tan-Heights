from pathlib import Path
import pytest
from src.security.authorization import HumanRoleRegistry, HumanPrincipal, AuthorizationPolicyEngine, PropertyScopedAuthorization, AuthorizationDenied
from src.security.audience import AudiencePolicyRegistry, AudienceEnforcer, AudienceDenied
from src.security.history import HistoricalReportAccessControl
ROOT=Path(__file__).resolve().parents[3]

def service():
    r=HumanRoleRegistry.from_repository(ROOT); p=AuthorizationPolicyEngine(r)
    a=AudienceEnforcer(audience_registry=AudiencePolicyRegistry(ROOT/'registries/security/audience-policy-v1.0.yaml'),role_registry=r)
    scope=PropertyScopedAuthorization(r,lambda s,prop:(s,prop) in {('seller','p1'),('agent','p1')})
    return HistoricalReportAccessControl(policy=p,property_scope=scope,audience=a)

def test_seller_current_access_does_not_grant_history():
    s=service(); principal=HumanPrincipal('seller','SELLER')
    d=s.require(principal,property_id='p1',report_id='r2',current_report_id='r2',report_variant='SELLER')
    assert d.is_current and d.action=='property.current_report.read'
    with pytest.raises(AuthorizationDenied): s.require(principal,property_id='p1',report_id='r1',current_report_id='r2',report_variant='SELLER')

def test_agent_can_read_assigned_history_but_not_other_property():
    s=service(); principal=HumanPrincipal('agent','AGENT')
    d=s.require(principal,property_id='p1',report_id='r1',current_report_id='r2',report_variant='AGENT')
    assert not d.is_current and d.action=='property.historical_report.read'
    with pytest.raises(AuthorizationDenied): s.require(principal,property_id='p2',report_id='r1',current_report_id='r2',report_variant='AGENT')

def test_lower_audience_cannot_use_history_to_cross_variant_boundary():
    with pytest.raises(AudienceDenied): service().require(HumanPrincipal('seller','SELLER'),property_id='p1',report_id='r1',current_report_id='r2',report_variant='AGENT')
