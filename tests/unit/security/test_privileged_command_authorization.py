from pathlib import Path
import pytest
from src.security.authorization import HumanRoleRegistry, HumanPrincipal, AuthorizationPolicyEngine, PropertyScopedAuthorization, AuthorizationDenied
from src.security.privileged import PrivilegedCommandRegistry, PrivilegedCommandAuthorization
ROOT=Path(__file__).resolve().parents[3]

def service():
    roles=HumanRoleRegistry.from_repository(ROOT)
    return PrivilegedCommandAuthorization(registry=PrivilegedCommandRegistry.from_repository(ROOT),policy=AuthorizationPolicyEngine(roles),property_scope=PropertyScopedAuthorization(roles,lambda s,p:False))

def test_agent_cannot_execute_recovery_or_publication_commands():
    s=service(); p=HumanPrincipal('agent','AGENT')
    for cmd in ['REQUEUE_REGENERATION_JOB','PUBLICATION_MANAGE']:
        with pytest.raises(AuthorizationDenied): s.require(p,command_type=cmd,property_id='p1')

def test_operations_can_execute_registered_privileged_commands():
    s=service(); p=HumanPrincipal('ops','OPERATIONS')
    assert s.require(p,command_type='REQUEUE_REGENERATION_JOB',property_id='p1').required_action=='recovery.execute'
    assert s.require(p,command_type='RELEASE_MANAGE').required_action=='release.manage'

def test_unknown_privileged_command_fails_closed():
    with pytest.raises(AuthorizationDenied): service().require(HumanPrincipal('admin','ADMIN'),command_type='DO_ANYTHING',property_id='p1')
