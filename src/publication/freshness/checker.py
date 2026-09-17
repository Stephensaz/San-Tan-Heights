from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class PrePublicationFreshnessResult:
    status: str
    reason_code: str | None = None

class PrePublicationVariantFreshness:
    """Reuses the variant semantic fingerprint check immediately before pointer mutation."""
    def __init__(self,variant_freshness_checker): self.variant_freshness_checker=variant_freshness_checker
    def check(self,cursor,*,report)->PrePublicationFreshnessResult:
        result=self.variant_freshness_checker.check(cursor,property_id=report.property_id,target_snapshot_id=report.snapshot_id,report_variant=report.report_variant)
        if result.status=='FRESH': return PrePublicationFreshnessResult('FRESH')
        if result.status=='STALE': return PrePublicationFreshnessResult('STALE',result.reason_code or 'PREPUBLICATION_VARIANT_STALE')
        return PrePublicationFreshnessResult('BLOCKED',result.reason_code or 'PREPUBLICATION_FRESHNESS_BLOCKED')
