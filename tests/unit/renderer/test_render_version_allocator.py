from uuid import uuid4
import pytest
from src.renderer.versioning import RenderVersionAllocator

class Cursor:
    def __init__(self,row): self.row=row; self.calls=[]
    def execute(self,sql,args): self.calls.append((sql,args))
    def fetchone(self): return self.row

def test_allocate_locks_counter_and_advances():
    c=Cursor((4,)); v=RenderVersionAllocator().allocate(c,uuid4(),'PDF')
    assert v==4
    assert any('FOR UPDATE' in sql for sql,_ in c.calls)
    assert c.calls[-1][1][0]==5

def test_no_max_version_pattern():
    assert 'MAX(' not in RenderVersionAllocator.LOCK.upper()

def test_counter_scoped_to_report_and_render_type():
    c=Cursor((1,)); rid=uuid4(); RenderVersionAllocator().allocate(c,rid,'WEB')
    assert c.calls[0][1] == (rid,'WEB')

def test_bad_render_type_rejected():
    with pytest.raises(ValueError): RenderVersionAllocator().allocate(Cursor((1,)),uuid4(),'RAW')
