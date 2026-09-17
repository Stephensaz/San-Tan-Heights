from uuid import uuid4
from src.dependency.lookup import DependencyReverseLookup

class Cursor:
    def __init__(self, rows): self.rows=list(rows); self.sql=[]
    def execute(self,sql,args): self.sql.append((sql,args))
    def fetchall(self): r=self.rows; self.rows=[]; return r

def test_snapshot_reverse_lookup_expands_variant_scope():
    p,s=uuid4(),uuid4(); c=Cursor([(p,s,None,'AGENT','a'*64),(p,s,None,'PUBLIC','a'*64)])
    result=DependencyReverseLookup().lookup_snapshot_consumers(c,'REAR_ADJACENCY','rear-1')
    assert [x.report_variant for x in result]==['AGENT','PUBLIC']
    assert 'current_snapshot_view' in c.sql[0][0]

def test_lookup_is_deterministic_and_normalizes_duplicate_consumers():
    p,s=uuid4(),uuid4()
    class MultiCursor(Cursor):
        def __init__(self): super().__init__([]); self.n=0
        def execute(self,sql,args): self.sql.append((sql,args)); self.n+=1; self.rows=[(p,s,None,'PUBLIC','b'*64)] if self.n==1 else [(p,s,None,'PUBLIC','b'*64)]
    result=DependencyReverseLookup().lookup(MultiCursor(),'POOL_STATUS','pool')
    assert len(result)==1
