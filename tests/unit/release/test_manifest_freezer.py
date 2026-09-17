from pathlib import Path
from uuid import uuid4
import pytest
from src.release.policy import ReleasePolicyRegistry
from src.release.membership import ReleaseCandidate, ReleaseScope, DeterministicMembershipResolver
from src.release.manifest import ReleaseManifestFreezer
ROOT=Path(__file__).resolve().parents[3]

def setup_manifest(target_hash='a'*64):
    policy=ReleasePolicyRegistry.from_repository(ROOT).get('STANDARD_FLEET'); rid=uuid4(); prop=uuid4()
    res=DeterministicMembershipResolver().resolve(candidates=[ReleaseCandidate(prop,'PUBLIC','WEB',target_report_id=uuid4(),target_semantic_fingerprint=target_hash,target_presentation_fingerprint='b'*64)],policy=policy)
    return ReleaseManifestFreezer().build(release_id=rid,policy=policy,scope=ReleaseScope(),resolution=res)

def test_manifest_freezes_exact_target_evidence_and_is_deterministic_for_same_inputs():
    p=ReleasePolicyRegistry.from_repository(ROOT).get('STANDARD_FLEET'); rid=uuid4(); prop=uuid4(); report=uuid4()
    c=ReleaseCandidate(prop,'PUBLIC','WEB',target_report_id=report,target_semantic_fingerprint='a'*64,target_presentation_fingerprint='b'*64)
    res=DeterministicMembershipResolver().resolve(candidates=[c],policy=p)
    a=ReleaseManifestFreezer().build(release_id=rid,policy=p,scope=ReleaseScope(),resolution=res)
    b=ReleaseManifestFreezer().build(release_id=rid,policy=p,scope=ReleaseScope(),resolution=res)
    assert a.manifest_fingerprint==b.manifest_fingerprint
    assert a.membership_fingerprint==b.membership_fingerprint
    assert a.manifest_payload['members'][0]['target_report_id']==str(report)
    assert a.total_item_count==1

def test_same_membership_but_changed_target_changes_manifest_not_membership():
    p=ReleasePolicyRegistry.from_repository(ROOT).get('STANDARD_FLEET'); rid=uuid4(); prop=uuid4()
    r=DeterministicMembershipResolver()
    r1=r.resolve(candidates=[ReleaseCandidate(prop,'PUBLIC','WEB',target_semantic_fingerprint='a'*64)],policy=p)
    r2=r.resolve(candidates=[ReleaseCandidate(prop,'PUBLIC','WEB',target_semantic_fingerprint='c'*64)],policy=p)
    f=ReleaseManifestFreezer()
    m1=f.build(release_id=rid,policy=p,scope=ReleaseScope(),resolution=r1); m2=f.build(release_id=rid,policy=p,scope=ReleaseScope(),resolution=r2)
    assert m1.membership_fingerprint==m2.membership_fingerprint
    assert m1.manifest_fingerprint!=m2.manifest_fingerprint

class Cursor:
    def __init__(self, rows): self.rows=list(rows); self.calls=[]
    def execute(self,sql,params=None): self.calls.append((sql,params))
    def fetchone(self): return self.rows.pop(0) if self.rows else None
class Repo:
    def __init__(self): self.items=[]; self.manifests=[]
    def insert_item(self,cursor,item): self.items.append(item)
    def insert_manifest(self,cursor,manifest): self.manifests.append(manifest)

def test_persist_is_idempotent_for_same_manifest_and_rejects_different_frozen_manifest():
    frozen=setup_manifest(); repo=Repo(); cur=Cursor([(frozen.release_id,),None])
    ReleaseManifestFreezer().persist(cur,repo,frozen)
    assert len(repo.items)==1 and len(repo.manifests)==1
    cur2=Cursor([(frozen.release_id,),(frozen.manifest_fingerprint,)])
    ReleaseManifestFreezer().persist(cur2,Repo(),frozen)
    other=setup_manifest('c'*64)
    # Force same parent release but different fingerprint.
    object.__setattr__(other,'release_id',frozen.release_id)
    cur3=Cursor([(frozen.release_id,),('d'*64,)])
    with pytest.raises(ValueError,match='already frozen'):
        ReleaseManifestFreezer().persist(cur3,Repo(),other)
