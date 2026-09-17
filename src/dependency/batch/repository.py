from __future__ import annotations
from uuid import UUID, uuid4
from .models import DependencyChangeBatch, DependencyChangeItem

class DependencyChangeBatchRepository:
    INSERT_BATCH='''INSERT INTO orchestration.dependency_change_batches
(batch_id,dependency_type,source_change_id,old_version,new_version,batch_state,correlation_id)
VALUES (%s,%s,%s,%s,%s,'DISCOVERING',%s)
ON CONFLICT(dependency_type,source_change_id) DO NOTHING RETURNING batch_id'''
    FIND_BATCH='''SELECT batch_id FROM orchestration.dependency_change_batches WHERE dependency_type=%s AND source_change_id=%s'''
    INSERT_ITEM='''INSERT INTO orchestration.dependency_change_items
(item_id,batch_id,property_id,dependency_id,old_fingerprint,new_fingerprint,change_class,required_state_blocked,item_state)
VALUES (%s,%s,%s,%s,%s,%s,%s,%s,'PENDING') ON CONFLICT(batch_id,property_id,dependency_id) DO NOTHING RETURNING item_id'''
    CLAIM_ITEMS='''SELECT item_id,batch_id,property_id,dependency_id,old_fingerprint,new_fingerprint,change_class,required_state_blocked
FROM orchestration.dependency_change_items WHERE batch_id=%s AND item_state='PENDING'
ORDER BY property_id,dependency_id FOR UPDATE SKIP LOCKED LIMIT %s'''
    MARK_EVALUATING="UPDATE orchestration.dependency_change_items SET item_state='EVALUATING' WHERE item_id = ANY(%s) AND item_state='PENDING'"
    COMPLETE_ITEM="UPDATE orchestration.dependency_change_items SET item_state='COMPLETE',result_summary=%s,evaluated_at=now(),last_error_code=NULL WHERE item_id=%s"
    FAIL_ITEM="UPDATE orchestration.dependency_change_items SET item_state='FAILED',last_error_code=%s,evaluated_at=now() WHERE item_id=%s"
    COUNTS='''SELECT item_state,count(*) FROM orchestration.dependency_change_items WHERE batch_id=%s GROUP BY item_state'''
    UPDATE_BATCH='''UPDATE orchestration.dependency_change_batches SET batch_state=%s,candidate_property_count=%s,evaluated_property_count=%s,affected_property_count=%s,completed_at=CASE WHEN %s IN ('COMPLETE','PARTIAL_FAILURE','BLOCKED') THEN now() ELSE NULL END WHERE batch_id=%s'''

    def create_batch(self,cursor,*,dependency_type,source_change_id,correlation_id,old_version=None,new_version=None):
        bid=uuid4(); cursor.execute(self.INSERT_BATCH,(bid,dependency_type,source_change_id,old_version,new_version,correlation_id)); row=cursor.fetchone()
        if row: return UUID(str(row[0]))
        cursor.execute(self.FIND_BATCH,(dependency_type,source_change_id)); row=cursor.fetchone()
        if not row: raise RuntimeError('batch conflict without existing batch')
        return UUID(str(row[0]))

    def add_item(self,cursor,*,batch_id,property_id,dependency_id,change_class,old_fingerprint=None,new_fingerprint=None,required_state_blocked=False):
        iid=uuid4(); cursor.execute(self.INSERT_ITEM,(iid,batch_id,property_id,dependency_id,old_fingerprint,new_fingerprint,change_class,required_state_blocked)); row=cursor.fetchone()
        return UUID(str(row[0])) if row else None

    def claim_items(self,cursor,batch_id:UUID,limit:int=250):
        cursor.execute(self.CLAIM_ITEMS,(batch_id,limit)); rows=cursor.fetchall()
        items=tuple(DependencyChangeItem(UUID(str(r[0])),UUID(str(r[1])),UUID(str(r[2])),str(r[3]),str(r[6]),r[4],r[5],bool(r[7])) for r in rows)
        if items: cursor.execute(self.MARK_EVALUATING,([x.item_id for x in items],))
        return items

    def complete_item(self,cursor,item_id,summary): cursor.execute(self.COMPLETE_ITEM,(summary,item_id))
    def fail_item(self,cursor,item_id,error_code): cursor.execute(self.FAIL_ITEM,(error_code,item_id))

    def reconcile_batch(self,cursor,batch_id:UUID,affected_items:int=0):
        cursor.execute(self.COUNTS,(batch_id,)); counts={str(state):int(count) for state,count in cursor.fetchall()}
        candidate=sum(counts.values()); evaluated=sum(counts.get(x,0) for x in ('COMPLETE','FAILED','BLOCKED'))
        if counts.get('FAILED',0): state='PARTIAL_FAILURE'
        elif counts.get('BLOCKED',0): state='BLOCKED'
        elif counts.get('PENDING',0) or counts.get('EVALUATING',0): state='EVALUATING'
        else: state='COMPLETE'
        cursor.execute(self.UPDATE_BATCH,(state,candidate,evaluated,affected_items,state,batch_id))
        return {'batch_state':state,'candidate_property_count':candidate,'evaluated_property_count':evaluated,'affected_property_count':affected_items,'item_state_counts':counts}
