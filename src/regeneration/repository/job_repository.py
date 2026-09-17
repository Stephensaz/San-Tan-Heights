from __future__ import annotations
from uuid import UUID
from .models import RegenerationJob

class RegenerationJobRepository:
    INSERT = '''INSERT INTO orchestration.regeneration_jobs
(job_id,property_id,report_variant,trigger_event_id,trigger_type,target_snapshot_id,old_report_id,priority_class,priority_score,job_target_key,job_state,attempt_count,max_attempts,worker_id,claimed_at,last_heartbeat_at,lease_expires_at,queued_at,started_at,completed_at,next_retry_at,input_hash,completion_report_id,failure_stage,failure_code,failure_message_safe,stale_reason_code,release_id,correlation_id)
VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,COALESCE(%s,now()),%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)'''
    FIND_ACTIVE = '''SELECT job_id FROM orchestration.regeneration_jobs
WHERE property_id=%s AND report_variant=%s AND job_target_key=%s
AND job_state IN ('QUEUED','CLAIMED','RUNNING','RETRY_WAIT')
ORDER BY queued_at ASC, job_id ASC LIMIT 1'''
    FIND_BY_ID = '''SELECT job_id,property_id,report_variant,trigger_type,target_snapshot_id,priority_class,priority_score,job_target_key,correlation_id,job_state,trigger_event_id,old_report_id,attempt_count,max_attempts,worker_id,claimed_at,last_heartbeat_at,lease_expires_at,queued_at,started_at,completed_at,next_retry_at,input_hash,completion_report_id,failure_stage,failure_code,failure_message_safe,stale_reason_code,release_id
FROM orchestration.regeneration_jobs WHERE job_id=%s'''


    CLAIM_NEXT = """WITH candidate AS (
        SELECT job_id FROM orchestration.regeneration_jobs
        WHERE (job_state='QUEUED' OR (job_state='RETRY_WAIT' AND (next_retry_at IS NULL OR next_retry_at <= now())))
        ORDER BY priority_score DESC, queued_at ASC, job_id ASC
        FOR UPDATE SKIP LOCKED
        LIMIT 1
    )
    UPDATE orchestration.regeneration_jobs j
       SET job_state='CLAIMED', worker_id=%s, claimed_at=now(), last_heartbeat_at=now(),
           lease_expires_at=%s, updated_at=now(), attempt_count=attempt_count+1
      FROM candidate c WHERE j.job_id=c.job_id
    RETURNING j.job_id,j.property_id,j.report_variant,j.trigger_type,j.target_snapshot_id,j.priority_class,j.priority_score,j.job_target_key,j.correlation_id,j.job_state,j.trigger_event_id,j.old_report_id,j.attempt_count,j.max_attempts,j.worker_id,j.claimed_at,j.last_heartbeat_at,j.lease_expires_at,j.queued_at,j.started_at,j.completed_at,j.next_retry_at,j.input_hash,j.completion_report_id,j.failure_stage,j.failure_code,j.failure_message_safe,j.stale_reason_code,j.release_id"""
    START_RUNNING = """UPDATE orchestration.regeneration_jobs SET job_state='RUNNING', started_at=COALESCE(started_at,now()), updated_at=now()
    WHERE job_id=%s AND worker_id=%s AND job_state='CLAIMED' AND lease_expires_at>now() RETURNING job_id"""
    HEARTBEAT = """UPDATE orchestration.regeneration_jobs SET last_heartbeat_at=now(), lease_expires_at=%s, updated_at=now()
    WHERE job_id=%s AND worker_id=%s AND job_state='RUNNING' AND lease_expires_at>now() RETURNING job_id"""
    SET_RETRY_WAIT = """UPDATE orchestration.regeneration_jobs SET job_state='RETRY_WAIT', worker_id=NULL, claimed_at=NULL, last_heartbeat_at=NULL, lease_expires_at=NULL, next_retry_at=%s, failure_stage=%s, failure_code=%s, failure_message_safe=%s, updated_at=now()
    WHERE job_id=%s AND worker_id=%s AND job_state IN ('CLAIMED','RUNNING') RETURNING attempt_count,max_attempts"""
    SET_FAILED = """UPDATE orchestration.regeneration_jobs SET job_state=%s, completed_at=now(), worker_id=NULL, claimed_at=NULL,last_heartbeat_at=NULL,lease_expires_at=NULL,failure_stage=%s,failure_code=%s,failure_message_safe=%s,updated_at=now()
    WHERE job_id=%s AND (%s IS NULL OR worker_id=%s) AND job_state IN ('CLAIMED','RUNNING','RETRY_WAIT') RETURNING job_id"""
    COMPLETE_SUCCESS = """UPDATE orchestration.regeneration_jobs SET job_state=%s, completed_at=now(), completion_report_id=%s, input_hash=%s, worker_id=NULL, claimed_at=NULL,last_heartbeat_at=NULL,lease_expires_at=NULL, updated_at=now() WHERE job_id=%s AND worker_id=%s AND job_state='RUNNING' RETURNING job_id"""
    MARK_STALE = """UPDATE orchestration.regeneration_jobs SET job_state='STALE', completed_at=now(), stale_reason_code=%s, worker_id=NULL, claimed_at=NULL,last_heartbeat_at=NULL,lease_expires_at=NULL,updated_at=now() WHERE job_id=%s AND worker_id=%s AND job_state IN ('CLAIMED','RUNNING') RETURNING job_id"""

    def insert(self, cursor, job: RegenerationJob) -> None:
        if job.job_state not in {'QUEUED','BLOCKED','STALE','CANCELLED'}:
            raise ValueError('new regeneration job must start in a non-running state')
        if len(job.job_target_key) != 64:
            raise ValueError('job_target_key must be a SHA-256 hex digest')
        cursor.execute(self.INSERT, (
            job.job_id, job.property_id, job.report_variant, job.trigger_event_id, job.trigger_type,
            job.target_snapshot_id, job.old_report_id, job.priority_class, job.priority_score,
            job.job_target_key, job.job_state, job.attempt_count, job.max_attempts, job.worker_id,
            job.claimed_at, job.last_heartbeat_at, job.lease_expires_at, job.queued_at,
            job.started_at, job.completed_at, job.next_retry_at, job.input_hash,
            job.completion_report_id, job.failure_stage, job.failure_code, job.failure_message_safe,
            job.stale_reason_code, job.release_id, job.correlation_id,
        ))

    def find_active(self, cursor, property_id: UUID, report_variant: str, job_target_key: str) -> UUID | None:
        cursor.execute(self.FIND_ACTIVE, (property_id, report_variant, job_target_key))
        row = cursor.fetchone()
        return UUID(str(row[0])) if row else None
    @staticmethod
    def _from_row(row):
        if row is None: return None
        return RegenerationJob(UUID(str(row[0])),UUID(str(row[1])),str(row[2]),str(row[3]),UUID(str(row[4])),str(row[5]),int(row[6]),str(row[7]),UUID(str(row[8])),
            job_state=str(row[9]), trigger_event_id=UUID(str(row[10])) if row[10] else None, old_report_id=UUID(str(row[11])) if row[11] else None,
            attempt_count=int(row[12]),max_attempts=int(row[13]),worker_id=row[14],claimed_at=row[15],last_heartbeat_at=row[16],lease_expires_at=row[17],queued_at=row[18],started_at=row[19],completed_at=row[20],next_retry_at=row[21],input_hash=row[22],completion_report_id=UUID(str(row[23])) if row[23] else None,failure_stage=row[24],failure_code=row[25],failure_message_safe=row[26],stale_reason_code=row[27],release_id=UUID(str(row[28])) if row[28] else None)

    def claim_next(self, cursor, worker_id: str, lease_expires_at):
        cursor.execute(self.CLAIM_NEXT,(worker_id,lease_expires_at)); return self._from_row(cursor.fetchone())

    def start_running(self,cursor,job_id: UUID,worker_id: str) -> bool:
        cursor.execute(self.START_RUNNING,(job_id,worker_id)); return cursor.fetchone() is not None

    def heartbeat(self,cursor,job_id: UUID,worker_id: str,lease_expires_at) -> bool:
        cursor.execute(self.HEARTBEAT,(lease_expires_at,job_id,worker_id)); return cursor.fetchone() is not None

    def set_retry_wait(self,cursor,job_id: UUID,worker_id: str,next_retry_at,failure_stage: str,failure_code: str,failure_message_safe: str|None):
        cursor.execute(self.SET_RETRY_WAIT,(next_retry_at,failure_stage,failure_code,failure_message_safe,job_id,worker_id)); return cursor.fetchone()

    def set_terminal_failure(self,cursor,job_id: UUID,state: str,failure_stage: str,failure_code: str,failure_message_safe: str|None,worker_id: str|None=None) -> bool:
        if state not in {'FAILED','BLOCKED'}: raise ValueError('terminal failure state must be FAILED or BLOCKED')
        cursor.execute(self.SET_FAILED,(state,failure_stage,failure_code,failure_message_safe,job_id,worker_id,worker_id)); return cursor.fetchone() is not None

    def complete_success(self,cursor,job_id: UUID,worker_id: str,report_id: UUID,input_hash: str,state: str='SUCCEEDED')->bool:
        if state not in {'SUCCEEDED','NO_OP'}: raise ValueError('success state must be SUCCEEDED or NO_OP')
        if len(input_hash)!=64: raise ValueError('input_hash must be a SHA-256 hex digest')
        cursor.execute(self.COMPLETE_SUCCESS,(state,report_id,input_hash,job_id,worker_id)); return cursor.fetchone() is not None

    def mark_stale(self,cursor,job_id: UUID,worker_id: str,reason_code: str)->bool:
        cursor.execute(self.MARK_STALE,(reason_code,job_id,worker_id)); return cursor.fetchone() is not None

