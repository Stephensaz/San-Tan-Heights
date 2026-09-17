from types import SimpleNamespace
from uuid import uuid4
from src.regeneration.freshness import VariantFreshnessChecker

class Cursor:
    def __init__(self,row): self.row=row; self.calls=[]
    def execute(self,sql,args): self.calls.append((sql,args))
    def fetchone(self): return self.row

class CurrentReader:
    def __init__(self,obj): self.obj=obj
    def get(self,cursor,property_id): return self.obj

def current(snapshot_id, a='a'*64,s='s'*64,p='p'*64):
    return SimpleNamespace(current_snapshot_id=snapshot_id,agent_semantic_fingerprint=a,seller_semantic_fingerprint=s,public_semantic_fingerprint=p)

def test_agent_only_change_does_not_stale_public():
    prop,target,current_id=uuid4(),uuid4(),uuid4()
    c=Cursor((target,'b'*64,'s'*64,'p'*64))
    result=VariantFreshnessChecker(CurrentReader(current(current_id,'a'*64,'s'*64,'p'*64))).check(c,property_id=prop,target_snapshot_id=target,report_variant='PUBLIC')
    assert result.status=='FRESH'
    assert result.target_fingerprint=='p'*64

def test_public_change_stales_public():
    prop,target,current_id=uuid4(),uuid4(),uuid4()
    c=Cursor((target,'a'*64,'s'*64,'p'*64))
    result=VariantFreshnessChecker(CurrentReader(current(current_id,'a'*64,'s'*64,'q'*64))).check(c,property_id=prop,target_snapshot_id=target,report_variant='PUBLIC')
    assert result.status=='STALE'
    assert result.reason_code=='VARIANT_SEMANTIC_FINGERPRINT_CHANGED'

def test_missing_target_blocks():
    target=uuid4(); c=Cursor(None)
    result=VariantFreshnessChecker(CurrentReader(None)).check(c,property_id=uuid4(),target_snapshot_id=target,report_variant='SELLER')
    assert result.status=='BLOCKED'
    assert result.reason_code=='TARGET_SNAPSHOT_NOT_FOUND'

def test_unknown_variant_fails_closed():
    import pytest
    c=Cursor((uuid4(),'a'*64,'s'*64,'p'*64))
    with pytest.raises(ValueError):
        VariantFreshnessChecker(CurrentReader(None)).check(c,property_id=uuid4(),target_snapshot_id=uuid4(),report_variant='OPS')
