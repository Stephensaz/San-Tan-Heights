from __future__ import annotations
from dataclasses import replace

class BulkGenerationCoordinator:
    """Queues generation for frozen release members without altering membership evidence."""
    def __init__(self,*,lifecycle,queue_report,queue_render=None): self.lifecycle=lifecycle; self.queue_report=queue_report; self.queue_render=queue_render
    def coordinate(self,cursor,*,items,actor='RELEASE_SERVICE',correlation_id=None):
        queued=[]; blocked=[]
        for item in items:
            if item.item_state not in {'PENDING','FAILED','BLOCKED'}: continue
            try:
                self.queue_report(cursor,item)
                if item.channel is not None and self.queue_render is not None: self.queue_render(cursor,item)
                self.lifecycle.transition(cursor,item=item,to_state='GENERATION_QUEUED',actor=actor,reason_code='RELEASE_GENERATION_QUEUED',correlation_id=correlation_id)
                queued.append(item.release_item_id)
            except Exception:
                # caller transaction decides commit/rollback; never rewrite target evidence here
                blocked.append(item.release_item_id)
        return {'queued':tuple(queued),'blocked':tuple(blocked)}
