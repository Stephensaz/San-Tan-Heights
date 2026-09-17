from pathlib import Path
import pytest
from src.security.audience import AudiencePolicyRegistry, AudienceEnforcer, AudienceDenied
from src.security.authorization.models import HumanPrincipal
from src.security.authorization.registry import HumanRoleRegistry

ROOT=Path(__file__).resolve().parents[3]

def engine():
    return AudienceEnforcer(
      audience_registry=AudiencePolicyRegistry(ROOT/'registries/security/audience-policy-v1.0.yaml'),
      role_registry=HumanRoleRegistry.from_repository(ROOT))

def test_public_cannot_request_seller_or_agent_variant():
    e=engine(); p=HumanPrincipal('anon','PUBLIC')
    assert e.require(p,report_variant='PUBLIC').response_dto=='PublicReportResponse'
    with pytest.raises(AudienceDenied): e.require(p,report_variant='SELLER')
    with pytest.raises(AudienceDenied): e.require(p,report_variant='AGENT')

def test_seller_cannot_request_agent_variant():
    e=engine(); p=HumanPrincipal('seller-1','SELLER')
    e.require(p,report_variant='SELLER')
    with pytest.raises(AudienceDenied): e.require(p,report_variant='AGENT')

def test_agent_and_operations_can_request_agent_variant():
    e=engine()
    assert e.require(HumanPrincipal('a','AGENT'),report_variant='AGENT').allowed
    assert e.require(HumanPrincipal('o','OPERATIONS'),report_variant='AGENT').allowed
