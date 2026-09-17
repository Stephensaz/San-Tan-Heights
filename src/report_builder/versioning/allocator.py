from __future__ import annotations
from uuid import UUID

class ReportVersionAllocator:
    ENSURE='''INSERT INTO reporting.report_version_counters(property_id,report_variant,next_version)
VALUES (%s,%s,1) ON CONFLICT (property_id,report_variant) DO NOTHING'''
    LOCK='''SELECT next_version FROM reporting.report_version_counters
WHERE property_id=%s AND report_variant=%s FOR UPDATE'''
    ADVANCE='''UPDATE reporting.report_version_counters SET next_version=%s,updated_at=now()
WHERE property_id=%s AND report_variant=%s'''

    def allocate(self,cursor,property_id: UUID,report_variant: str)->int:
        if report_variant not in {'AGENT','SELLER','PUBLIC'}: raise ValueError('unsupported report variant')
        cursor.execute(self.ENSURE,(property_id,report_variant))
        cursor.execute(self.LOCK,(property_id,report_variant)); row=cursor.fetchone()
        if row is None: raise RuntimeError('report version counter unavailable')
        version=int(row[0])
        if version < 1: raise RuntimeError('invalid report version counter')
        cursor.execute(self.ADVANCE,(version+1,property_id,report_variant))
        return version
