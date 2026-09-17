from uuid import uuid4
from src.snapshot.dedup import SnapshotDeduplicator
class Repo:
    def __init__(self, value): self.value=value
    def find_equivalent(self,c,p,f): return self.value

def test_new_snapshot_required_when_none_exists():
    r=SnapshotDeduplicator(Repo(None)).check(None,uuid4(),'a'*64); assert r.status=='NEW_SNAPSHOT_REQUIRED'

def test_existing_equivalent_reused():
    sid=uuid4(); r=SnapshotDeduplicator(Repo(sid)).check(None,uuid4(),'a'*64); assert r.status=='EXISTING_EQUIVALENT' and r.snapshot_id==sid
