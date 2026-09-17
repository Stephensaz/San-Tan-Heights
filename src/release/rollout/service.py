from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class FailureDecision:
    action:str
    failed:int
    succeeded:int

class PartialFailurePolicyEngine:
    def __init__(self,*,max_failed_count=0,max_failed_ratio=0.0): self.max_count=max_failed_count; self.max_ratio=max_failed_ratio
    def evaluate(self,*,failed,succeeded):
        total=failed+succeeded; ratio=(failed/total) if total else 0.0
        action='CONTINUE' if failed<=self.max_count and ratio<=self.max_ratio else 'HALT'
        return FailureDecision(action,failed,succeeded)

class ChunkedPublicationService:
    def __init__(self,*,lifecycle,publish_item,policy_engine,chunk_size=100):
        if chunk_size<=0: raise ValueError('chunk_size must be positive')
        self.lifecycle=lifecycle; self.publish_item=publish_item; self.policy=policy_engine; self.chunk_size=chunk_size
    def publish(self,cursor,*,items,actor='RELEASE_SERVICE',correlation_id=None):
        succeeded=failed=0; halted=False
        eligible=[i for i in items if i.item_state=='APPROVED']
        for pos in range(0,len(eligible),self.chunk_size):
            for item in eligible[pos:pos+self.chunk_size]:
                self.lifecycle.transition(cursor,item=item,to_state='PUBLISHING',actor=actor,reason_code='RELEASE_ITEM_PUBLISHING',correlation_id=correlation_id)
                result=self.publish_item(cursor,item)
                if getattr(result,'status',result)=='PUBLISHED':
                    # use lightweight state proxy because caller's immutable item still says APPROVED
                    proxy=type('I',(),{**item.__dict__,'item_state':'PUBLISHING'})()
                    self.lifecycle.transition(cursor,item=proxy,to_state='PUBLISHED',actor=actor,reason_code='RELEASE_ITEM_PUBLISHED',correlation_id=correlation_id); succeeded+=1
                else:
                    proxy=type('I',(),{**item.__dict__,'item_state':'PUBLISHING'})()
                    self.lifecycle.transition(cursor,item=proxy,to_state='FAILED',actor=actor,reason_code=getattr(result,'reason_code',None) or 'RELEASE_ITEM_PUBLICATION_FAILED',correlation_id=correlation_id); failed+=1
            if self.policy.evaluate(failed=failed,succeeded=succeeded).action=='HALT': halted=True; break
        return {'published':succeeded,'failed':failed,'halted':halted}
