from __future__ import annotations
from dataclasses import dataclass

from src.security.authorization import (
    AuthorizationPolicyEngine,
    PropertyScopedAuthorization,
    HumanPrincipal,
)
from src.security.audience.enforcement import AudienceEnforcer

VARIANT_CLASSIFICATION = {
    "PUBLIC": "PUBLIC_DATA",
    "SELLER": "SELLER_DATA",
    "AGENT": "AGENT_INTERNAL",
}

@dataclass(frozen=True)
class ReportAccessDecision:
    report_id: str
    is_current: bool
    action: str
    classification: str

class HistoricalReportAccessControl:
    """Current-report permission never implies historical-report permission."""
    def __init__(self, *, policy: AuthorizationPolicyEngine, property_scope: PropertyScopedAuthorization, audience: AudienceEnforcer):
        self.policy = policy
        self.property_scope = property_scope
        self.audience = audience

    def require(self, principal: HumanPrincipal, *, property_id: str, report_id: str, current_report_id: str | None, report_variant: str) -> ReportAccessDecision:
        self.audience.require(principal, report_variant=report_variant)
        classification = VARIANT_CLASSIFICATION.get(report_variant)
        if not classification:
            from src.security.authorization import AuthorizationDenied
            raise AuthorizationDenied("UNKNOWN_REPORT_VARIANT")
        is_current = current_report_id is not None and str(report_id) == str(current_report_id)
        action = "property.current_report.read" if is_current else "property.historical_report.read"
        decision = self.policy.require(principal, action=action, classification=classification)
        self.property_scope.require(principal, decision, property_id=property_id)
        return ReportAccessDecision(str(report_id), is_current, action, classification)
