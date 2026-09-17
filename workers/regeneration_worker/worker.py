from __future__ import annotations
from dataclasses import dataclass
from uuid import UUID
from src.regeneration.worker import RegenerationLeaseManager
from src.regeneration.repository import RegenerationJobRepository

@dataclass(frozen=True)
class ReportBuildOutcome:
    report_id: UUID
    report_input_hash: str
    reused_existing: bool
    validation_valid: bool
    failure_code: str | None = None

class RegenerationWorker:
    """Owns queue lifecycle; delegates report semantics to the injected build service."""
    def __init__(self,worker_id: str,lease_manager=None,repository=None,freshness_checker=None,build_service=None,retry_service=None):
        self.worker_id=worker_id
        self.leases=lease_manager or RegenerationLeaseManager()
        self.repository=repository or RegenerationJobRepository()
        self.freshness_checker=freshness_checker
        self.build_service=build_service
        self.retry_service=retry_service
    def claim(self,cursor): return self.leases.claim_next(cursor,self.worker_id)
    def start(self,cursor,job_id): return self.leases.start(cursor,job_id,self.worker_id)
    def heartbeat(self,cursor,job_id): return self.leases.heartbeat(cursor,job_id,self.worker_id)
    def process(self,cursor,job):
        if not self.start(cursor,job.job_id):
            return 'LEASE_LOST'
        if self.freshness_checker is None or self.build_service is None:
            raise RuntimeError('worker integration requires freshness_checker and build_service')
        fresh=self.freshness_checker.check(cursor,property_id=job.property_id,target_snapshot_id=job.target_snapshot_id,report_variant=job.report_variant)
        if fresh.status=='STALE':
            self.repository.mark_stale(cursor,job.job_id,self.worker_id,fresh.reason_code or 'VARIANT_SEMANTIC_FINGERPRINT_CHANGED')
            return 'STALE'
        if fresh.status=='BLOCKED':
            self.repository.set_terminal_failure(cursor,job.job_id,'BLOCKED','FRESHNESS',fresh.reason_code or 'FRESHNESS_BLOCKED',None,self.worker_id)
            return 'BLOCKED'
        try:
            outcome=self.build_service.build_and_persist(cursor,job)
        except Exception as exc:
            if self.retry_service is None: raise
            code=getattr(exc,'failure_code','REPORT_BUILD_FAILED')
            self.retry_service.handle_failure(cursor,job_id=job.job_id,worker_id=self.worker_id,failure_stage='REPORT_BUILD',failure_code=code,failure_message_safe=type(exc).__name__,attempt_count=job.attempt_count,max_attempts=job.max_attempts)
            return 'FAILED_OR_RETRY'
        if not outcome.validation_valid:
            if self.retry_service is None:
                self.repository.set_terminal_failure(cursor,job.job_id,'BLOCKED','REPORT_VALIDATION',outcome.failure_code or 'REPORT_VALIDATION_FAILED',None,self.worker_id)
            else:
                self.retry_service.handle_failure(cursor,job_id=job.job_id,worker_id=self.worker_id,failure_stage='REPORT_VALIDATION',failure_code=outcome.failure_code or 'REPORT_VALIDATION_FAILED',failure_message_safe=None,attempt_count=job.attempt_count,max_attempts=job.max_attempts)
            return 'VALIDATION_FAILED'
        state='NO_OP' if outcome.reused_existing else 'SUCCEEDED'
        self.repository.complete_success(cursor,job.job_id,self.worker_id,outcome.report_id,outcome.report_input_hash,state)
        return state
