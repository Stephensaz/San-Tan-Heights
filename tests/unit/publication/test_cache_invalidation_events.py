from uuid import uuid4
from src.publication.cache import CacheInvalidationEvents
class W:
    def __init__(self): self.events=[]
    def write(self,c,e): self.events.append(e)

def test_cache_invalidation_keys_are_stable_and_event_is_emitted():
    p=uuid4(); w=W(); s=CacheInvalidationEvents(w)
    payload=s.emit(None,property_id=p,report_variant='PUBLIC',channel='WEB',reason_code='PUBLISHED')
    assert payload['cache_keys']==[f'property:{p}:report:PUBLIC',f'property:{p}:report:PUBLIC:channel:WEB']
    assert w.events[0].event_type=='PUBLICATION_CACHE_INVALIDATED'
