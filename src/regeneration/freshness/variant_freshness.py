from __future__ import annotations
from dataclasses import dataclass
from uuid import UUID

VARIANT_ATTR = {
    'AGENT': 'agent_semantic_fingerprint',
    'SELLER': 'seller_semantic_fingerprint',
    'PUBLIC': 'public_semantic_fingerprint',
}

@dataclass(frozen=True)
class FreshnessResult:
    status: str  # FRESH | STALE | BLOCKED
    report_variant: str
    target_snapshot_id: UUID
    current_snapshot_id: UUID | None
    target_fingerprint: str | None
    current_fingerprint: str | None
    reason_code: str | None = None

class VariantFreshnessChecker:
    """Compares only the semantic fingerprint relevant to the requested audience."""
    TARGET_SQL = '''SELECT snapshot_id,agent_semantic_fingerprint,seller_semantic_fingerprint,public_semantic_fingerprint
    FROM snapshot.intelligence_snapshots WHERE snapshot_id=%s AND property_id=%s'''

    def __init__(self, current_snapshots):
        self.current_snapshots = current_snapshots

    @staticmethod
    def _fp(obj, variant: str) -> str:
        attr = VARIANT_ATTR.get(variant)
        if attr is None:
            raise ValueError('unsupported report variant')
        return str(getattr(obj, attr))

    def check(self, cursor, *, property_id: UUID, target_snapshot_id: UUID, report_variant: str) -> FreshnessResult:
        attr = VARIANT_ATTR.get(report_variant)
        if attr is None:
            raise ValueError('unsupported report variant')
        cursor.execute(self.TARGET_SQL, (target_snapshot_id, property_id))
        row = cursor.fetchone()
        if row is None:
            return FreshnessResult('BLOCKED', report_variant, target_snapshot_id, None, None, None, 'TARGET_SNAPSHOT_NOT_FOUND')
        target = type('Target', (), {
            'snapshot_id': UUID(str(row[0])),
            'agent_semantic_fingerprint': str(row[1]),
            'seller_semantic_fingerprint': str(row[2]),
            'public_semantic_fingerprint': str(row[3]),
        })()
        current = self.current_snapshots.get(cursor, property_id)
        if current is None:
            return FreshnessResult('BLOCKED', report_variant, target_snapshot_id, None, self._fp(target, report_variant), None, 'CURRENT_SNAPSHOT_NOT_FOUND')
        target_fp = self._fp(target, report_variant)
        current_fp = self._fp(current, report_variant)
        if target_fp == current_fp:
            return FreshnessResult('FRESH', report_variant, target_snapshot_id, current.current_snapshot_id, target_fp, current_fp)
        return FreshnessResult('STALE', report_variant, target_snapshot_id, current.current_snapshot_id, target_fp, current_fp, 'VARIANT_SEMANTIC_FINGERPRINT_CHANGED')
