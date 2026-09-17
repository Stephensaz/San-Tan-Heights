from __future__ import annotations
from .models import PublicationStage

class PublicationStagingRepository:
    INSERT='''INSERT INTO publication.publication_staging
(staging_id,property_id,report_variant,channel,report_id,render_id,staging_state,requested_by,reason_code,correlation_id)
VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
ON CONFLICT (property_id,report_variant,channel,report_id,render_id) DO NOTHING'''
    UPDATE_STATE='''UPDATE publication.publication_staging SET staging_state=%s,reason_code=%s,updated_at=now()
WHERE staging_id=%s AND staging_state=%s RETURNING staging_id'''
    LOCK='''SELECT staging_id,property_id,report_variant,channel,report_id,render_id,staging_state,requested_by,reason_code,correlation_id,created_at
FROM publication.publication_staging WHERE staging_id=%s FOR UPDATE'''
    VALID_VARIANTS={'AGENT','SELLER','PUBLIC'}
    VALID_CHANNELS={'WEB','PDF_DOWNLOAD','PRINT'}
    VALID_STATES={'STAGED','VALIDATING','READY','PUBLISHED','BLOCKED','FAILED','STALE','CANCELLED'}
    def insert(self,cursor,stage:PublicationStage)->None:
        if stage.report_variant not in self.VALID_VARIANTS: raise ValueError('unsupported report variant')
        if stage.channel not in self.VALID_CHANNELS: raise ValueError('unsupported publication channel')
        if stage.staging_state not in self.VALID_STATES: raise ValueError('unsupported staging state')
        cursor.execute(self.INSERT,(stage.staging_id,stage.property_id,stage.report_variant,stage.channel,stage.report_id,stage.render_id,stage.staging_state,stage.requested_by,stage.reason_code,stage.correlation_id))
    def transition(self,cursor,staging_id,*,from_state:str,to_state:str,reason_code:str|None=None)->bool:
        if from_state not in self.VALID_STATES or to_state not in self.VALID_STATES: raise ValueError('unsupported staging state')
        cursor.execute(self.UPDATE_STATE,(to_state,reason_code,staging_id,from_state)); return cursor.fetchone() is not None
    def lock(self,cursor,staging_id):
        cursor.execute(self.LOCK,(staging_id,)); return cursor.fetchone()
