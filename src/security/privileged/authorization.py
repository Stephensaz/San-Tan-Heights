from __future__ import annotations
from dataclasses import dataclass
from src.security.authorization import AuthorizationPolicyEngine, PropertyScopedAuthorization, HumanPrincipal, AuthorizationDenied
from .registry import PrivilegedCommandRegistry, PrivilegedCommandRegistryError

@dataclass(frozen=True)
class PrivilegedCommandDecision:
    command_type: str
    required_action: str
    classification: str
    property_scoped: bool

class PrivilegedCommandAuthorization:
    def __init__(self, *, registry: PrivilegedCommandRegistry, policy: AuthorizationPolicyEngine, property_scope: PropertyScopedAuthorization):
        self.registry=registry; self.policy=policy; self.property_scope=property_scope
    def require(self, principal: HumanPrincipal, *, command_type: str, property_id: str | None = None) -> PrivilegedCommandDecision:
        try: rule=self.registry.get(command_type)
        except PrivilegedCommandRegistryError as exc: raise AuthorizationDenied(str(exc)) from exc
        decision=self.policy.require(principal,action=rule.required_action,classification=rule.classification)
        if rule.property_scoped:
            self.property_scope.require(principal,decision,property_id=property_id)
        return PrivilegedCommandDecision(rule.command_type,rule.required_action,rule.classification,rule.property_scoped)
