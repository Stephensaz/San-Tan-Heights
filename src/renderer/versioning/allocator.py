from __future__ import annotations
from uuid import UUID


class RenderVersionAllocator:
    """Allocate render versions without MAX(version)+1 races."""

    VALID_TYPES = {'WEB', 'PDF', 'PRINT', 'MOBILE_PREVIEW'}
    ENSURE = '''INSERT INTO reporting.render_version_counters(report_id,render_type,next_version)
VALUES (%s,%s,1) ON CONFLICT (report_id,render_type) DO NOTHING'''
    LOCK = '''SELECT next_version FROM reporting.render_version_counters
WHERE report_id=%s AND render_type=%s FOR UPDATE'''
    ADVANCE = '''UPDATE reporting.render_version_counters SET next_version=%s,updated_at=now()
WHERE report_id=%s AND render_type=%s'''

    def allocate(self, cursor, report_id: UUID, render_type: str) -> int:
        if render_type not in self.VALID_TYPES:
            raise ValueError('unsupported render type')
        cursor.execute(self.ENSURE, (report_id, render_type))
        cursor.execute(self.LOCK, (report_id, render_type))
        row = cursor.fetchone()
        if row is None:
            raise RuntimeError('render version counter unavailable')
        version = int(row[0])
        if version < 1:
            raise RuntimeError('invalid render version counter')
        cursor.execute(self.ADVANCE, (version + 1, report_id, render_type))
        return version
