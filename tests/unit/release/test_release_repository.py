from uuid import uuid4
import pytest
from src.release.repository import ReleaseItemRecord, ReleaseManifestRecord, ReleaseRecord, ReleaseRepository


class Cursor:
    def __init__(self): self.calls=[]
    def execute(self, sql, params=None): self.calls.append((sql,params))


def test_insert_release_targets_operations_release_parent_and_canonicalizes_scope_json():
    c=Cursor(); r=ReleaseRecord(uuid4(), release_scope={'z':1,'a':2})
    ReleaseRepository().insert_release(c,r)
    sql,params=c.calls[0]
    assert 'INSERT INTO operations.releases' in sql
    assert params[3] == '{"a":2,"z":1}'


def test_release_parent_fails_closed_on_unknown_state_or_bad_hash():
    repo=ReleaseRepository()
    with pytest.raises(ValueError): repo.insert_release(Cursor(),ReleaseRecord(uuid4(),release_state='MAGIC'))
    with pytest.raises(ValueError): repo.insert_release(Cursor(),ReleaseRecord(uuid4(),membership_fingerprint='bad'))


def test_manifest_persists_exact_fingerprints_and_canonical_payload():
    c=Cursor(); rid=uuid4()
    rec=ReleaseManifestRecord(rid,'a'*64,'b'*64,{'items':[2,1],'release_id':str(rid)})
    ReleaseRepository().insert_manifest(c,rec)
    sql,params=c.calls[0]
    assert 'INSERT INTO operations.release_manifests' in sql
    assert params[1:3] == ('a'*64,'b'*64)
    assert params[3].startswith('{"items"')


def test_release_item_validates_variant_channel_ordinal_and_hashes():
    repo=ReleaseRepository(); base=dict(release_item_id=uuid4(),release_id=uuid4(),property_id=uuid4(),report_variant='PUBLIC',membership_ordinal=1)
    c=Cursor(); repo.insert_item(c,ReleaseItemRecord(**base,channel='WEB',target_semantic_fingerprint='c'*64))
    assert 'INSERT INTO operations.release_items' in c.calls[0][0]
    with pytest.raises(ValueError): repo.insert_item(Cursor(),ReleaseItemRecord(**{**base,'report_variant':'PRIVATE'}))
    with pytest.raises(ValueError): repo.insert_item(Cursor(),ReleaseItemRecord(**base,channel='EMAIL'))
    with pytest.raises(ValueError): repo.insert_item(Cursor(),ReleaseItemRecord(**{**base,'membership_ordinal':0}))
