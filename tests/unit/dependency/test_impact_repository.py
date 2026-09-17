from uuid import uuid4
from src.dependency.repository import ImpactRepository
from src.dependency.evaluator import ImpactDecision

class Cursor:
    def __init__(self, results): self.results=list(results); self.calls=[]
    def execute(self,sql,args): self.calls.append((sql,args))
    def fetchone(self): return self.results.pop(0) if self.results else None

def decision():
    return ImpactDecision(uuid4(),None,'PUBLIC','REAR_ADJACENCY','rear','a'*64,'b'*64,'NORMAL_UPDATE','DIRTY','IMPACT_REAR_ADJACENCY_001','DEPENDENCY_SEMANTIC_CHANGE')

def test_persist_returns_inserted_id():
    iid=uuid4(); c=Cursor([(iid,)])
    assert ImpactRepository().persist(c,source_event_id=uuid4(),correlation_id=uuid4(),decision=decision(),rule_version='1.0.0')==iid

def test_duplicate_same_decision_reuses_existing():
    iid=uuid4(); c=Cursor([None,(iid,'DIRTY','DEPENDENCY_SEMANTIC_CHANGE')])
    assert ImpactRepository().persist(c,source_event_id=uuid4(),correlation_id=uuid4(),decision=decision(),rule_version='1.0.0')==iid
