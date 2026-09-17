from __future__ import annotations
class ReleaseCancellationService:
    CANCELLABLE={'PENDING','GENERATION_QUEUED','GENERATING','GENERATED','VALIDATED','STAGED','APPROVED','BLOCKED','FAILED'}
    def __init__(self,*,lifecycle): self.lifecycle=lifecycle
    def cancel(self,cursor,*,items,actor='RELEASE_SERVICE',reason_code='RELEASE_CANCELLED',correlation_id=None):
        if any(i.item_state in {'PUBLISHING','PUBLISHED','ROLLED_BACK'} for i in items): raise ValueError('release with publication activity requires rollback, not cancellation')
        n=0
        for i in items:
            if i.item_state in self.CANCELLABLE:
                self.lifecycle.transition(cursor,item=i,to_state='CANCELLED',actor=actor,reason_code=reason_code,correlation_id=correlation_id); n+=1
        return n
