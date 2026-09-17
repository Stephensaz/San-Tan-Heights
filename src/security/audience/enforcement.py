from __future__ import annotations
from dataclasses import dataclass
from src.security.authorization.models import HumanPrincipal
from src.security.authorization.registry import HumanRoleRegistry, HumanRoleRegistryError
from .registry import AudiencePolicyRegistry, AudiencePolicyRegistryError

class AudienceDenied(PermissionError):
    pass

@dataclass(frozen=True)
class AudienceDecision:
    allowed: bool
    role_id: str
    report_variant: str
    response_dto: str | None
    reason: str

class AudienceEnforcer:
    """Fail-closed audience gate. Property authorization is intentionally separate."""
    def __init__(self, *, audience_registry: AudiencePolicyRegistry, role_registry: HumanRoleRegistry):
        self.audience_registry = audience_registry
        self.role_registry = role_registry

    def evaluate(self, principal: HumanPrincipal, *, report_variant: str) -> AudienceDecision:
        try:
            audience = self.audience_registry.get(principal.role_id)
            role = self.role_registry.get(principal.role_id)
        except (AudiencePolicyRegistryError, HumanRoleRegistryError) as exc:
            return AudienceDecision(False, principal.role_id, report_variant, None, str(exc))
        if role.status != "ACTIVE":
            return AudienceDecision(False, role.role_id, report_variant, None, "ROLE_DISABLED")
        if report_variant not in audience.report_variants:
            return AudienceDecision(False, role.role_id, report_variant, None, "AUDIENCE_VARIANT_DENIED")
        if not audience.required_classifications <= role.classifications:
            return AudienceDecision(False, role.role_id, report_variant, None, "AUDIENCE_CLASSIFICATION_MISMATCH")
        return AudienceDecision(True, role.role_id, report_variant, audience.response_dto, "ALLOW")

    def require(self, principal: HumanPrincipal, *, report_variant: str) -> AudienceDecision:
        decision = self.evaluate(principal, report_variant=report_variant)
        if not decision.allowed:
            raise AudienceDenied(decision.reason)
        return decision
