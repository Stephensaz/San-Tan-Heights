from uuid import uuid4
from src.dependency.batch import DependencyChangeBatchRepository

class Cursor:
    def __init__(self, rows): self.rows=list(rows); self.calls=[]
    def execute(self,sql,args): self.calls.append((sql,args))
    def fetchone(self): return self.rows.pop(0) if self.rows else None
    def fetchall(self): return self.rows.pop(0) if self.rows else []

def test_create_batch_is_idempotent():
    existing=uuid4(); c=Cursor([None,(existing,)])
    got=DependencyChangeBatchRepository().create_batch(c,dependency_type='PARCEL_GEOMETRY',source_change_id='source-1',correlation_id=uuid4())
    assert got==existing

def test_add_duplicate_item_is_noop():
    c=Cursor([None])
    got=DependencyChangeBatchRepository().add_item(c,batch_id=uuid4(),property_id=uuid4(),dependency_id='p1',change_class='NORMAL_UPDATE')
    assert got is None

def test_claim_query_is_deterministic_and_skip_locked():
    repo=DependencyChangeBatchRepository(); assert 'ORDER BY property_id,dependency_id' in repo.CLAIM_ITEMS; assert 'SKIP LOCKED' in repo.CLAIM_ITEMS

def test_reconcile_batch_derives_partial_failure_from_items():
    bid=uuid4(); c=Cursor([[('COMPLETE',8),('FAILED',1),('PENDING',1)]])
    out=DependencyChangeBatchRepository().reconcile_batch(c,bid,affected_items=6)
    assert out['batch_state']=='PARTIAL_FAILURE'
    assert out['candidate_property_count']==10
    assert out['evaluated_property_count']==9
    assert out['affected_property_count']==6
