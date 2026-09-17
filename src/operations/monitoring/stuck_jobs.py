from datetime import datetime, timezone, timedelta
from .models import IntegrityFinding
class StuckJobDetector:
    def __init__(self, *, queued_threshold=timedelta(hours=2), lease_grace=timedelta(minutes=5)):
        self.queued_threshold=queued_threshold; self.lease_grace=lease_grace
    def detect(self,jobs,*,now=None):
        now=now or datetime.now(timezone.utc); out=[]
        for j in jobs:
            state=j['job_state']; stuck=False; detail=''
            if state in ('QUEUED','RETRY_READY') and now-j['queued_at']>self.queued_threshold:
                stuck=True; detail='job exceeded queue age threshold'
            elif state in ('CLAIMED','RUNNING') and j.get('lease_expires_at') and now-j['lease_expires_at']>self.lease_grace:
                stuck=True; detail='job lease expired beyond grace period'
            if stuck: out.append(IntegrityFinding('STUCK_REGENERATION_JOB','regeneration_job',j['job_id'],'FAIL',detail))
        return tuple(out)
