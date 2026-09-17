from __future__ import annotations
from dataclasses import dataclass
from uuid import UUID

@dataclass(frozen=True)
class PublicationFreeze:
    freeze_id: UUID
    property_id: UUID
    report_variant: str
    channel: str | None
    reason_code: str
    created_by: str

class PublicationFreezeRepository:
    INSERT='''INSERT INTO publication.publication_freezes
(freeze_id,property_id,report_variant,channel,reason_code,created_by)
VALUES (%s,%s,%s,%s,%s,%s)'''
    RELEASE='''UPDATE publication.publication_freezes SET released_at=now(),released_by=%s
WHERE freeze_id=%s AND released_at IS NULL RETURNING freeze_id'''
    CHECK='''SELECT freeze_id,reason_code FROM (
SELECT freeze_id,reason_code,created_at FROM operations.global_publication_freezes WHERE released_at IS NULL
UNION ALL
SELECT freeze_id,reason_code,created_at FROM publication.publication_freezes
WHERE property_id=%s AND report_variant=%s AND released_at IS NULL
AND (channel IS NULL OR channel=%s)
) active_freezes ORDER BY created_at DESC LIMIT 1'''
    def create(self,cursor,freeze:PublicationFreeze):
        cursor.execute(self.INSERT,(freeze.freeze_id,freeze.property_id,freeze.report_variant,freeze.channel,freeze.reason_code,freeze.created_by))
    def release(self,cursor,freeze_id:UUID,actor:str)->bool:
        cursor.execute(self.RELEASE,(actor,freeze_id)); return cursor.fetchone() is not None
    def active(self,cursor,property_id:UUID,report_variant:str,channel:str):
        cursor.execute(self.CHECK,(property_id,report_variant,channel)); row=cursor.fetchone()
        return None if not row else (UUID(str(row[0])),str(row[1]))
