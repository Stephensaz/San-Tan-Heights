from uuid import uuid4
from src.snapshot.repository import *
H='b'*64
class C:
    def __init__(self): self.calls=[]
    def execute(self,s,p=None): self.calls.append((s,p))

def test_snapshot_repository_is_insert_only():
    c=C(); r=SnapshotRecord(uuid4(),uuid4(),1,'TEST','g','tok','i','gov','m',H,H,H,H,H,'COMPLETE','PASS','tester')
    SnapshotRepository().insert(c,r); assert len(c.calls)==1 and 'INSERT INTO snapshot.intelligence_snapshots' in c.calls[0][0]

def test_child_repositories_insert_expected_tables():
    sid=uuid4(); c=C()
    SnapshotFindingRepository().insert(c,SnapshotFindingRecord(uuid4(),sid,'F','TYPE','P','1',H,{'x':1},'VERIFIED','PASS','PRODUCTION_READY','ALL','a','s','p','1','1','1',H,H))
    SnapshotDependencyRepository().insert(c,SnapshotDependencyRecord(uuid4(),sid,'PROPERTY_IDENTITY','D',H,H,'1',True,True,True,True))
    SnapshotRequirementRepository().insert(c,SnapshotRequirementResultRecord(uuid4(),sid,'REQ','CORE',True,'SATISFIED'))
    SnapshotDiffRepository().insert(c,SnapshotDiffRecord(uuid4(),uuid4(),sid,{'x':1},H))
    sql=' '.join(x[0] for x in c.calls)
    for table in ['snapshot.snapshot_findings','snapshot.snapshot_dependencies','snapshot.snapshot_requirement_results','snapshot.snapshot_diffs']: assert table in sql
