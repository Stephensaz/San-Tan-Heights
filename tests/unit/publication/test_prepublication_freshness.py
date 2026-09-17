from types import SimpleNamespace as NS
from uuid import uuid4
from src.publication.freshness import PrePublicationVariantFreshness

class Checker:
    def __init__(self,status,reason=None): self.result=NS(status=status,reason_code=reason); self.calls=[]
    def check(self,cursor,**kwargs): self.calls.append(kwargs); return self.result

def report(): return NS(property_id=uuid4(),snapshot_id=uuid4(),report_variant='SELLER')

def test_freshness_delegates_exact_variant_and_snapshot():
    c=Checker('FRESH'); r=report(); out=PrePublicationVariantFreshness(c).check(object(),report=r)
    assert out.status=='FRESH' and c.calls[0]['report_variant']=='SELLER' and c.calls[0]['target_snapshot_id']==r.snapshot_id

def test_stale_and_blocked_are_preserved():
    assert PrePublicationVariantFreshness(Checker('STALE','X')).check(object(),report=report()).status=='STALE'
    assert PrePublicationVariantFreshness(Checker('BLOCKED','Y')).check(object(),report=report()).status=='BLOCKED'
