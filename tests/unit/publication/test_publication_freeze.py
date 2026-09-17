from uuid import uuid4
from src.publication.freeze import PublicationFreezeRepository, PublicationFreeze

class C:
    def __init__(self,rows=None): self.calls=[]; self.rows=list(rows or [])
    def execute(self,s,p=None): self.calls.append((s,p))
    def fetchone(self): return self.rows.pop(0) if self.rows else None

def test_freeze_repository_is_scope_aware_and_releasable():
    p,f=uuid4(),uuid4(); c=C([(f,'LEGAL_HOLD')]) ; r=PublicationFreezeRepository()
    assert r.active(c,p,'PUBLIC','WEB')[1]=='LEGAL_HOLD'
    c2=C([(f,)])
    assert r.release(c2,f,'OPS') is True

def test_freeze_model_supports_variant_wide_or_channel_specific_scope():
    x=PublicationFreeze(uuid4(),uuid4(),'PUBLIC',None,'DATA_REVIEW','OPS')
    assert x.channel is None
