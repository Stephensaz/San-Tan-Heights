from __future__ import annotations
from dataclasses import dataclass
from uuid import UUID

@dataclass(frozen=True)
class DependencyConsumer:
    property_id: UUID
    snapshot_id: UUID | None
    report_id: UUID | None
    report_variant: str
    stored_semantic_fingerprint: str

class DependencyReverseLookup:
    SNAPSHOT_SQL = '''SELECT s.property_id,d.snapshot_id,NULL::uuid AS report_id,v.report_variant,d.semantic_fingerprint
FROM snapshot.snapshot_dependencies d
JOIN snapshot.current_snapshot_view s ON s.current_snapshot_id=d.snapshot_id
CROSS JOIN LATERAL (VALUES
 ('AGENT',d.affects_agent),('SELLER',d.affects_seller),('PUBLIC',d.affects_public)
) AS v(report_variant, affected)
WHERE d.dependency_type=%s AND d.dependency_id=%s AND v.affected=true
ORDER BY s.property_id,v.report_variant'''

    REPORT_SQL = '''SELECT r.property_id,d.snapshot_id,d.report_id,r.report_variant,d.semantic_fingerprint
FROM reporting.report_dependencies d
JOIN reporting.report_versions r ON r.report_id=d.report_id
WHERE d.dependency_type=%s AND d.dependency_id=%s
ORDER BY r.property_id,r.report_variant'''

    def lookup_snapshot_consumers(self, cursor, dependency_type: str, dependency_id: str):
        cursor.execute(self.SNAPSHOT_SQL,(dependency_type,dependency_id))
        return self._rows(cursor.fetchall())

    def lookup_report_consumers(self, cursor, dependency_type: str, dependency_id: str):
        try:
            cursor.execute(self.REPORT_SQL,(dependency_type,dependency_id))
        except Exception:
            return ()
        return self._rows(cursor.fetchall())

    def lookup(self, cursor, dependency_type: str, dependency_id: str):
        seen={}
        for c in (*self.lookup_snapshot_consumers(cursor,dependency_type,dependency_id), *self.lookup_report_consumers(cursor,dependency_type,dependency_id)):
            key=(c.property_id,c.report_variant,c.report_id,c.snapshot_id)
            seen[key]=c
        return tuple(sorted(seen.values(), key=lambda x:(str(x.property_id),x.report_variant,str(x.report_id or ''),str(x.snapshot_id or ''))))

    @staticmethod
    def _rows(rows):
        return tuple(DependencyConsumer(UUID(str(r[0])), UUID(str(r[1])) if r[1] else None, UUID(str(r[2])) if r[2] else None, str(r[3]), str(r[4])) for r in rows)
