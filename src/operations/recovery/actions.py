from __future__ import annotations
from uuid import UUID

class ExplicitRecoveryActions:
    """Explicit operator-invoked actions only. No action is selected automatically here."""
    def __init__(self,freeze_repository=None,incident_lifecycle=None): self.freezes=freeze_repository; self.incidents=incident_lifecycle
    def execute(self,cursor,*,incident,command_type,payload,actor):
        if command_type=='RELEASE_PUBLICATION_FREEZE':
            if not self.freezes: return {'status':'BLOCKED','reason':'FREEZE_REPOSITORY_UNAVAILABLE'}
            released=self.freezes.release(cursor,UUID(str(payload['freeze_id'])),actor)
            return {'status':'SUCCEEDED' if released else 'NO_OP','action':'RELEASE_PUBLICATION_FREEZE'}
        if command_type=='REQUEUE_REGENERATION_JOB':
            cursor.execute("""UPDATE orchestration.regeneration_jobs SET job_state='QUEUED',worker_id=NULL,lease_expires_at=NULL,next_attempt_at=NULL,updated_at=now() WHERE job_id=%s AND job_state IN ('FAILED','BLOCKED','STALE') RETURNING job_id""",(UUID(str(payload['job_id'])),))
            return {'status':'SUCCEEDED' if cursor.fetchone() else 'NO_OP','action':'REQUEUE_REGENERATION_JOB'}
        if command_type=='RETRY_RELEASE_ITEM':
            cursor.execute("""UPDATE operations.release_items SET item_state='GENERATION_QUEUED',last_error_code=NULL,updated_at=now() WHERE release_item_id=%s AND item_state IN ('FAILED','BLOCKED') RETURNING release_item_id""",(UUID(str(payload['release_item_id'])),))
            return {'status':'SUCCEEDED' if cursor.fetchone() else 'NO_OP','action':'RETRY_RELEASE_ITEM'}
        if command_type=='REVALIDATE_PUBLICATION_TARGET':
            return {'status':'SUCCEEDED','action':'REVALIDATE_PUBLICATION_TARGET','property_id':str(payload['property_id']),'report_variant':payload['report_variant'],'channel':payload['channel']}
        if command_type=='RESOLVE_INCIDENT':
            if not self.incidents:return {'status':'BLOCKED','reason':'INCIDENT_LIFECYCLE_UNAVAILABLE'}
            self.incidents.transition(cursor,incident=incident,to_state='RESOLVED',reason_code='INCIDENT_RECOVERED',actor=actor)
            return {'status':'SUCCEEDED','action':'RESOLVE_INCIDENT'}
        raise ValueError('unsupported recovery command type')
