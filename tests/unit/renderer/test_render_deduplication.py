from uuid import uuid4
from src.renderer.deduplication import RenderDeduplicationEngine

class Repo:
    def __init__(self, found=None): self.found=found; self.calls=[]
    def find_equivalent(self,cursor,report_id,render_type,presentation_input_hash):
        self.calls.append((report_id,render_type,presentation_input_hash)); return self.found

def test_reuses_exact_presentation_identity():
    rid=uuid4(); repo=Repo(rid); e=RenderDeduplicationEngine(repo)
    d=e.decide(object(),report_id=uuid4(),render_type='WEB',presentation_input_hash='a'*64)
    assert d.action=='REUSE' and d.existing_render_id==rid

def test_creates_when_no_equivalent_render_exists():
    d=RenderDeduplicationEngine(Repo()).decide(object(),report_id=uuid4(),render_type='PDF',presentation_input_hash='b'*64)
    assert d.action=='CREATE' and d.existing_render_id is None
