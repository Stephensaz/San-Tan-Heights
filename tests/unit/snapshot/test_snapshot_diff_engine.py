from uuid import uuid4
from src.snapshot.diff import SnapshotDiffEngine
from src.snapshot.repository.models import SnapshotFindingRecord, SnapshotDependencyRecord

A='a'*64; B='b'*64; C='c'*64

def finding(fid='f1', value=None, fp=A, confidence='VERIFIED', scope='ALL', public='Public'):
    return SnapshotFindingRecord(
        uuid4(), uuid4(), fid, 'REAR_ADJACENCY', 'p', 'v', A,
        value if value is not None else {'code':'LOT'}, confidence, 'PASS', 'PRODUCTION_READY', scope,
        'Agent', 'Seller', public, '1', '1', '1', fp, B
    )

def dep(ver='1', sem=A, rec=B):
    return SnapshotDependencyRecord(uuid4(), uuid4(), 'PROPERTY_IDENTITY', 'd1', rec, sem, ver, True, True, True, True)

def test_diff_value_and_hash_deterministic():
    engine=SnapshotDiffEngine(); old_id=uuid4(); new_id=uuid4()
    old=finding(); new=finding(value={'code':'COMMON'}, fp=C)
    a=engine.compare(old_snapshot_id=old_id,new_snapshot_id=new_id,old_findings=[old],new_findings=[new])
    b=engine.compare(old_snapshot_id=old_id,new_snapshot_id=new_id,old_findings=[old],new_findings=[new])
    assert a.diff_payload['finding_changes'][0]['change_type']=='VALUE_CHANGED'
    assert a.diff_hash==b.diff_hash

def test_nonsemantic_dependency_version_distinguished():
    result=SnapshotDiffEngine().compare(old_snapshot_id=uuid4(),new_snapshot_id=uuid4(),old_dependencies=[dep()],new_dependencies=[dep(ver='2',rec=C)])
    assert result.diff_payload['dependency_changes'][0]['change_type']=='VERSION_CHANGED_NON_SEMANTIC'

def test_unchanged_findings_omitted():
    item=finding()
    result=SnapshotDiffEngine().compare(old_snapshot_id=uuid4(),new_snapshot_id=uuid4(),old_findings=[item],new_findings=[item])
    assert result.diff_payload['finding_changes']==[]
