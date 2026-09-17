from .models import AuthorizationDecision, HumanPrincipal
from .registry import HumanRoleRegistry, HumanRoleRegistryError

class AuthorizationDenied(PermissionError): pass

class AuthorizationPolicyEngine:
    def __init__(self, registry: HumanRoleRegistry): self.registry=registry
    def evaluate(self, principal: HumanPrincipal, *, action: str, classification: str) -> AuthorizationDecision:
        try:
            role=self.registry.get(principal.role_id); action_policy=self.registry.action(action)
        except HumanRoleRegistryError as exc:
            return AuthorizationDecision(False,principal.role_id,action,classification,False,str(exc))
        protected=bool(action_policy.get('protected_property'))
        if role.status!='ACTIVE': return AuthorizationDecision(False,role.role_id,action,classification,protected,'ROLE_DISABLED')
        if action not in role.actions and '*' not in role.actions: return AuthorizationDecision(False,role.role_id,action,classification,protected,'ACTION_DENIED')
        if classification not in role.classifications: return AuthorizationDecision(False,role.role_id,action,classification,protected,'CLASSIFICATION_DENIED')
        return AuthorizationDecision(True,role.role_id,action,classification,protected,'ALLOW')
    def require(self, principal: HumanPrincipal, *, action: str, classification: str) -> AuthorizationDecision:
        decision=self.evaluate(principal,action=action,classification=classification)
        if not decision.allowed: raise AuthorizationDenied(decision.reason)
        return decision
