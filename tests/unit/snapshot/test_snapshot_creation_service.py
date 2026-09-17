from dataclasses import replace
from uuid import uuid4
import pytest
from src.snapshot.service import SnapshotCreationService, SnapshotCreationError
from src.snapshot.requirements import load_snapshot_requirement_registry
from src.snapshot.findings import FindingFreezer
from src.snapshot.fingerprints import FindingFingerprintEngine
from src.snapshot.passports import PassportReference
from tests.unit.snapshot._fixtures import state, finding, dep
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]

class Client:
    def __init__(self, states): self.states=list(states); self.calls=0
    def get(self,pid): self.calls+=1; return self.states[min(self.calls-1,len(self.states)-1)]
class SnapRepo:
    def __init__(self,existing=None): self.existing=existing; self.inserted=[]; self.seq=1
    def find_equivalent(self,c,p,f): return self.existing
    def allocate_sequence(self,c,p): return self.seq
    def current_accepted(self,c,p): return None
    def insert(self,c,r): self.inserted.append(r)
class Repo:
    def __init__(self): self.inserted=[]
    def insert(self,c,r): self.inserted.append(r)

def prepared_state(token='token-1'):
    f=finding('f1','REAR_ADJACENCY')
    frozen=FindingFreezer().freeze((f,))[0]
    pref=PassportReference(frozen.passport_id,frozen.passport_version,'c'*64,'PASS',frozen.finding_id,frozen.evidence_reference_set_hash)
    fp=FindingFingerprintEngine().calculate(frozen,pref)
    f=replace(f,semantic_fingerprint=fp)
    base=state(findings=(f,),dependencies=(dep('PROPERTY_IDENTITY','pid'),dep('PARCEL_IDENTITY','parcel')))
    return replace(base,source_read_token=token), pref

def build(client,pref,snap=None):
    repos=[Repo(),Repo(),Repo()]
    svc=SnapshotCreationService(governed_state_client=client,requirements=load_snapshot_requirement_registry(ROOT),passport_resolver=lambda p,v: pref,snapshot_repository=snap or SnapRepo(),finding_repository=repos[0],dependency_repository=repos[1],requirement_repository=repos[2])
    return svc,repos

def test_create_snapshot_persists_atomic_children_through_shared_cursor_contract():
    s,pref=prepared_state(); snap=SnapRepo(); svc,repos=build(Client([s,s]),pref,snap); cursor=object()
    result=svc.create(cursor,property_id=s.property_id,snapshot_reason='TEST',created_by='tester')
    assert result.status=='CREATED' and len(snap.inserted)==1
    assert len(repos[0].inserted)==1 and len(repos[1].inserted)==2
    assert len(repos[2].inserted) > 0

def test_equivalent_snapshot_returns_existing_without_allocating_or_children():
    s,pref=prepared_state(); existing=uuid4(); snap=SnapRepo(existing); svc,repos=build(Client([s,s]),pref,snap)
    result=svc.create(object(),property_id=s.property_id,snapshot_reason='TEST',created_by='tester')
    assert result.status=='EXISTING_EQUIVALENT' and result.snapshot_id==existing
    assert not snap.inserted and all(not r.inserted for r in repos)

def test_mid_capture_token_change_creates_no_snapshot():
    s,pref=prepared_state('t1'); latest=replace(s,source_read_token='t2'); snap=SnapRepo(); svc,repos=build(Client([s,latest]),pref,snap)
    with pytest.raises(SnapshotCreationError,match='SOURCE_STATE_CHANGED_DURING_CAPTURE'):
        svc.create(object(),property_id=s.property_id,snapshot_reason='TEST',created_by='tester')
    assert not snap.inserted and all(not r.inserted for r in repos)
