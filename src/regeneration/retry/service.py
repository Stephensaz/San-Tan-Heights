from __future__ import annotations
from datetime import datetime,timedelta,timezone
from pathlib import Path
from uuid import UUID
from src.regeneration.repository import RegenerationJobRepository
from .policy import RetryPolicy, RetryDecision

class RegenerationRetryService:
    def __init__(self,root: Path,repository=None,policy=None): self.repository=repository or RegenerationJobRepository(); self.policy=policy or RetryPolicy.from_repository(root)
    def handle_failure(self,cursor,*,job_id: UUID,worker_id: str,failure_stage: str,failure_code: str,failure_message_safe: str|None,attempt_count: int,max_attempts: int,now=None) -> RetryDecision:
        decision=self.policy.classify(failure_code,attempt_count,max_attempts)
        if decision.action=='RETRY':
            when=(now or datetime.now(timezone.utc))+timedelta(seconds=decision.delay_seconds or 0)
            self.repository.set_retry_wait(cursor,job_id,worker_id,when,failure_stage,failure_code,failure_message_safe)
        else:
            state='BLOCKED' if decision.action=='BLOCK' else 'FAILED'
            self.repository.set_terminal_failure(cursor,job_id,state,failure_stage,failure_code,failure_message_safe,worker_id)
        return decision
