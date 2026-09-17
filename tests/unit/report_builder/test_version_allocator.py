from uuid import uuid4
import pytest
from src.report_builder.versioning import ReportVersionAllocator

class Cursor:
    def __init__(self,row): self.row=row; self.calls=[]
    def execute(self,sql,args): self.calls.append((sql,args))
    def fetchone(self): return self.row

def test_allocate_locks_counter_and_advances():
    c=Cursor((7,)); v=ReportVersionAllocator().allocate(c,uuid4(),'AGENT')
    assert v==7
    assert any('FOR UPDATE' in sql for sql,_ in c.calls)
    assert c.calls[-1][1][0]==8

def test_no_max_version_pattern():
    assert 'MAX(' not in ReportVersionAllocator.LOCK.upper()

def test_bad_variant_rejected():
    with pytest.raises(ValueError): ReportVersionAllocator().allocate(Cursor((1,)),uuid4(),'OPS')
