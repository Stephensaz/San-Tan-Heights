from __future__ import annotations
from uuid import UUID
from .models import CurrentReportPointer, ChannelPointer, PublicationHistoryRecord

class PublicationRepository:
    LOCK_TARGET = '''SELECT pg_advisory_xact_lock(hashtextextended(%s,0))'''
    UPSERT_CURRENT = '''INSERT INTO publication.report_current
(property_id,report_variant,report_id,pointer_version,updated_by)
VALUES (%s,%s,%s,%s,%s)
ON CONFLICT (property_id,report_variant) DO UPDATE SET
report_id=EXCLUDED.report_id,pointer_version=publication.report_current.pointer_version+1,updated_at=now(),updated_by=EXCLUDED.updated_by'''
    GET_CURRENT = '''SELECT report_id,pointer_version FROM publication.report_current
WHERE property_id=%s AND report_variant=%s'''
    UPSERT_CHANNEL = '''INSERT INTO publication.channel_pointers
(property_id,report_variant,channel,report_id,render_id,pointer_version,updated_by)
VALUES (%s,%s,%s,%s,%s,%s,%s)
ON CONFLICT (property_id,report_variant,channel) DO UPDATE SET
report_id=EXCLUDED.report_id,render_id=EXCLUDED.render_id,pointer_version=publication.channel_pointers.pointer_version+1,updated_at=now(),updated_by=EXCLUDED.updated_by'''
    GET_CHANNEL = '''SELECT report_id,render_id,pointer_version FROM publication.channel_pointers
WHERE property_id=%s AND report_variant=%s AND channel=%s'''
    INSERT_HISTORY='''INSERT INTO publication.publication_history
(property_id,report_variant,channel,report_id,render_id,action,reason_code,correlation_id,actor)
VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)'''
    CLEAR_CHANNEL='''DELETE FROM publication.channel_pointers WHERE property_id=%s AND report_variant=%s AND channel=%s'''
    CLEAR_CURRENT='''DELETE FROM publication.report_current WHERE property_id=%s AND report_variant=%s'''
    LIST_CHANNELS_FOR_REPORT='''SELECT channel,render_id FROM publication.channel_pointers WHERE property_id=%s AND report_variant=%s AND report_id=%s ORDER BY channel'''
    WAS_PUBLISHED='''SELECT 1 FROM publication.publication_history WHERE property_id=%s AND report_variant=%s AND channel=%s AND report_id=%s AND render_id=%s AND action IN ('PUBLISHED','REPUBLISHED','RENDER_PROMOTED','ROLLED_BACK') LIMIT 1'''

    def lock_target(self,cursor,property_id:UUID,report_variant:str,channel:str)->None:
        self._variant(report_variant); self._channel(channel)
        cursor.execute(self.LOCK_TARGET,(f'publication:{property_id}:{report_variant}:{channel}',))

    def set_current_report(self, cursor, pointer: CurrentReportPointer) -> None:
        self._variant(pointer.report_variant)
        cursor.execute(self.UPSERT_CURRENT, (pointer.property_id,pointer.report_variant,pointer.report_id,pointer.pointer_version,pointer.updated_by))
    def get_current_report(self, cursor, property_id: UUID, report_variant: str):
        self._variant(report_variant); cursor.execute(self.GET_CURRENT,(property_id,report_variant)); row=cursor.fetchone()
        return None if not row else (UUID(str(row[0])), int(row[1]))
    def set_channel_pointer(self, cursor, pointer: ChannelPointer) -> None:
        self._variant(pointer.report_variant); self._channel(pointer.channel)
        cursor.execute(self.UPSERT_CHANNEL,(pointer.property_id,pointer.report_variant,pointer.channel,pointer.report_id,pointer.render_id,pointer.pointer_version,pointer.updated_by))
    def get_channel_pointer(self, cursor, property_id: UUID, report_variant: str, channel: str):
        self._variant(report_variant); self._channel(channel); cursor.execute(self.GET_CHANNEL,(property_id,report_variant,channel)); row=cursor.fetchone()
        return None if not row else (UUID(str(row[0])), UUID(str(row[1])), int(row[2]))
    def append_history(self,cursor,record:PublicationHistoryRecord)->None:
        self._variant(record.report_variant)
        if record.channel is not None: self._channel(record.channel)
        cursor.execute(self.INSERT_HISTORY,(record.property_id,record.report_variant,record.channel,record.report_id,record.render_id,record.action,record.reason_code,record.correlation_id,record.actor))

    def lock_semantic_target(self,cursor,property_id:UUID,report_variant:str)->None:
        self._variant(report_variant)
        cursor.execute(self.LOCK_TARGET,(f'publication:{property_id}:{report_variant}:SEMANTIC',))

    def clear_channel_pointer(self,cursor,property_id:UUID,report_variant:str,channel:str)->None:
        self._variant(report_variant); self._channel(channel)
        cursor.execute(self.CLEAR_CHANNEL,(property_id,report_variant,channel))

    def clear_current_report(self,cursor,property_id:UUID,report_variant:str)->None:
        self._variant(report_variant)
        cursor.execute(self.CLEAR_CURRENT,(property_id,report_variant))

    def list_channel_pointers_for_report(self,cursor,property_id:UUID,report_variant:str,report_id:UUID):
        self._variant(report_variant)
        cursor.execute(self.LIST_CHANNELS_FOR_REPORT,(property_id,report_variant,report_id))
        rows=cursor.fetchall() if hasattr(cursor,'fetchall') else []
        return tuple((str(r[0]),UUID(str(r[1]))) for r in rows)

    def was_previously_published(self,cursor,property_id:UUID,report_variant:str,channel:str,report_id:UUID,render_id:UUID)->bool:
        self._variant(report_variant); self._channel(channel)
        cursor.execute(self.WAS_PUBLISHED,(property_id,report_variant,channel,report_id,render_id))
        return cursor.fetchone() is not None
    @staticmethod
    def _variant(value: str):
        if value not in {'AGENT','SELLER','PUBLIC'}: raise ValueError('unsupported report variant')
    @staticmethod
    def _channel(value: str):
        if value not in {'WEB','PDF_DOWNLOAD','PRINT'}: raise ValueError('unsupported publication channel')
