from __future__ import annotations
from datetime import datetime,timedelta,timezone
from uuid import UUID
from src.regeneration.repository import RegenerationJobRepository

class RegenerationLeaseManager:
    def __init__(self, repository=None, lease_seconds: int=120):
        if lease_seconds<30: raise ValueError('lease_seconds must be at least 30')
        self.repository=repository or RegenerationJobRepository(); self.lease_seconds=lease_seconds
    def _expiry(self, now=None): return (now or datetime.now(timezone.utc))+timedelta(seconds=self.lease_seconds)
    def claim_next(self,cursor,worker_id: str,now=None):
        if not worker_id.strip(): raise ValueError('worker_id is required')
        return self.repository.claim_next(cursor,worker_id,self._expiry(now))
    def start(self,cursor,job_id: UUID,worker_id: str) -> bool: return self.repository.start_running(cursor,job_id,worker_id)
    def heartbeat(self,cursor,job_id: UUID,worker_id: str,now=None) -> bool: return self.repository.heartbeat(cursor,job_id,worker_id,self._expiry(now))
