from __future__ import annotations
from dataclasses import dataclass

from src.security.authorization import (
    AuthorizationPolicyEngine,
    PropertyScopedAuthorization,
    HumanPrincipal,
    AuthorizationDenied,
)

MEDIA_CLASSIFICATIONS = {
    "PUBLIC": "PUBLIC_DATA",
    "SELLER": "SELLER_DATA",
    "AGENT": "AGENT_INTERNAL",
    "OPERATIONS": "OPERATIONS_INTERNAL",
    "RESTRICTED": "RESTRICTED",
}

@dataclass(frozen=True)
class PrivateMediaResource:
    media_id: str
    property_id: str
    visibility: str
    approval_status: str = "APPROVED"
    rights_status: str = "CLEARED"

class PrivateMediaAuthorization:
    """Authorizes access to non-public media independently of render slot binding."""
    def __init__(self, policy: AuthorizationPolicyEngine, property_scope: PropertyScopedAuthorization):
        self.policy = policy
        self.property_scope = property_scope

    def require(self, principal: HumanPrincipal, resource: PrivateMediaResource):
        classification = MEDIA_CLASSIFICATIONS.get(resource.visibility)
        if not classification:
            raise AuthorizationDenied("MEDIA_VISIBILITY_UNKNOWN")
        if resource.approval_status != "APPROVED":
            raise AuthorizationDenied("MEDIA_NOT_APPROVED")
        if resource.rights_status != "CLEARED":
            raise AuthorizationDenied("MEDIA_RIGHTS_NOT_CLEARED")
        decision = self.policy.require(
            principal,
            action="property.media.read",
            classification=classification,
        )
        self.property_scope.require(principal, decision, property_id=resource.property_id)
        return decision
