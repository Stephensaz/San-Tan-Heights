from typing import Callable
from .models import HumanPrincipal, AuthorizationDecision
from .registry import HumanRoleRegistry
from .policy import AuthorizationDenied

class PropertyScopedAuthorization:
    def __init__(self, registry: HumanRoleRegistry, assignment_checker: Callable[[str,str], bool]):
        self.registry=registry; self.assignment_checker=assignment_checker
    def require(self, principal: HumanPrincipal, decision: AuthorizationDecision, *, property_id: str|None) -> None:
        if not decision.allowed: raise AuthorizationDenied(decision.reason)
        if not decision.protected_property: return
        if not property_id: raise AuthorizationDenied('PROPERTY_ID_REQUIRED')
        mode=self.registry.get(principal.role_id).property_scope_mode
        if mode=='FLEET': return
        if mode=='ASSIGNED' and self.assignment_checker(principal.subject_id,property_id): return
        raise AuthorizationDenied('PROPERTY_SCOPE_DENIED')
