from __future__ import annotations
from dataclasses import dataclass

ITEM_TRANSITIONS={
 'PENDING':{'GENERATION_QUEUED','BLOCKED','CANCELLED'},
 'GENERATION_QUEUED':{'GENERATING','BLOCKED','FAILED','CANCELLED'},
 'GENERATING':{'GENERATED','BLOCKED','FAILED','CANCELLED'},
 'GENERATED':{'VALIDATED','BLOCKED','FAILED','CANCELLED'},
 'VALIDATED':{'STAGED','BLOCKED','CANCELLED'},
 'STAGED':{'APPROVED','BLOCKED','CANCELLED'},
 'APPROVED':{'PUBLISHING','BLOCKED','CANCELLED'},
 'PUBLISHING':{'PUBLISHED','FAILED','BLOCKED'},
 'PUBLISHED':{'ROLLED_BACK'},
 'BLOCKED':{'GENERATION_QUEUED','VALIDATED','STAGED','APPROVED','CANCELLED'},
 'FAILED':{'GENERATION_QUEUED','CANCELLED'},
 'ROLLED_BACK':set(),'CANCELLED':set(),
}
TERMINAL={'PUBLISHED','ROLLED_BACK','CANCELLED'}

@dataclass(frozen=True)
class TransitionResult:
    status:str
    from_state:str
    to_state:str

class ReleaseItemLifecycle:
    UPDATE="""UPDATE operations.release_items SET item_state=%s,last_error_code=%s,updated_at=now() WHERE release_item_id=%s AND item_state=%s"""
    HISTORY="""INSERT INTO operations.release_item_history (release_item_id,release_id,from_state,to_state,reason_code,actor,correlation_id) VALUES (%s,%s,%s,%s,%s,%s,%s)"""
    def transition(self,cursor,*,item, to_state, actor='RELEASE_SERVICE', reason_code=None, correlation_id=None):
        allowed=ITEM_TRANSITIONS.get(item.item_state)
        if allowed is None or to_state not in allowed: raise ValueError(f'illegal release item transition {item.item_state}->{to_state}')
        cursor.execute(self.UPDATE,(to_state,reason_code,item.release_item_id,item.item_state))
        if getattr(cursor,'rowcount',1)!=1: raise RuntimeError('release item state changed concurrently')
        cursor.execute(self.HISTORY,(item.release_item_id,item.release_id,item.item_state,to_state,reason_code,actor,correlation_id))
        return TransitionResult('TRANSITIONED',item.item_state,to_state)

RELEASE_TRANSITIONS={
 'DRAFT':{'ASSEMBLING','CANCELLED'},
 'ASSEMBLING':{'GENERATION_READY','BLOCKED','CANCELLED'},
 'GENERATION_READY':{'GENERATING','BLOCKED','CANCELLED'},
 'GENERATING':{'VALIDATING','BLOCKED','PARTIAL_FAILURE','CANCELLED'},
 'VALIDATING':{'STAGED','BLOCKED','PARTIAL_FAILURE','CANCELLED'},
 'STAGED':{'APPROVED','BLOCKED','CANCELLED'},
 'APPROVED':{'PUBLISHING','BLOCKED','CANCELLED'},
 'PUBLISHING':{'PUBLISHED','PARTIAL_FAILURE','BLOCKED','ROLLING_BACK'},
 'PUBLISHED':{'ROLLING_BACK'},
 'PARTIAL_FAILURE':{'ROLLING_BACK','CANCELLED'},
 'BLOCKED':{'ASSEMBLING','GENERATION_READY','VALIDATING','STAGED','CANCELLED'},
 'ROLLING_BACK':{'ROLLED_BACK','BLOCKED'},
 'ROLLED_BACK':set(),'CANCELLED':set(),
}

class ReleaseLifecycle:
    UPDATE="UPDATE operations.releases SET release_state=%s,reason_code=%s,updated_at=now() WHERE release_id=%s AND release_state=%s"
    def transition(self,cursor,*,release,to_state,reason_code=None):
        if to_state not in RELEASE_TRANSITIONS.get(release.release_state,set()):
            raise ValueError(f'illegal release transition {release.release_state}->{to_state}')
        cursor.execute(self.UPDATE,(to_state,reason_code,release.release_id,release.release_state))
        if getattr(cursor,'rowcount',1)!=1: raise RuntimeError('release state changed concurrently')
        return TransitionResult('TRANSITIONED',release.release_state,to_state)
