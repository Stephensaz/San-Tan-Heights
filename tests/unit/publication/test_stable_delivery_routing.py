from uuid import uuid4
from src.publication.routing import StableDeliveryRouter
class R:
    def __init__(self,val): self.val=val
    def get_channel_pointer(self,*args): return self.val

def test_stable_route_uses_pointer_not_versioned_url():
    p,r,rr=uuid4(),uuid4(),uuid4(); x=StableDeliveryRouter(R((r,rr,7))).resolve(None,property_id=p,report_variant='PUBLIC',channel='WEB')
    assert str(p) in x.path and 'public' in x.path and not x.path.endswith('/7') and '/versions/7' not in x.path
    assert x.report_id==r and x.render_id==rr

def test_missing_pointer_returns_no_delivery():
    assert StableDeliveryRouter(R(None)).resolve(None,property_id=uuid4(),report_variant='SELLER',channel='PDF_DOWNLOAD') is None
