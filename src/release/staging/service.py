from __future__ import annotations
class ReleaseStagingService:
    def __init__(self,*,lifecycle): self.lifecycle=lifecycle
    def stage(self,cursor,*,items,actor='RELEASE_SERVICE',correlation_id=None):
        if not items: raise ValueError('release has no items')
        if any(i.item_state!='VALIDATED' for i in items): raise ValueError('all release items must be VALIDATED before staging')
        for i in items:self.lifecycle.transition(cursor,item=i,to_state='STAGED',actor=actor,reason_code='RELEASE_STAGED',correlation_id=correlation_id)
        return len(items)
