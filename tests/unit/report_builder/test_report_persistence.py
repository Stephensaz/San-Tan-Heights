from uuid import uuid4
import pytest
from src.report_builder.repository import ReportRepository, ReportVersion, ReportDependency

class Cursor:
    def __init__(self,row=None): self.row=row; self.calls=[]
    def execute(self,sql,args): self.calls.append((sql,args))
    def fetchone(self): return self.row

def report(**kw):
    d=dict(report_id=uuid4(),property_id=uuid4(),report_variant='PUBLIC',version_number=1,snapshot_id=uuid4(),report_schema_version='1.0',content_contract_version='1.0',variant_policy_version='1.0',builder_version='0.1',report_input_hash='a'*64,canonical_payload_hash='b'*64,canonical_payload={'ok':True},dependency_manifest_hash='c'*64,generation_reason='TEST')
    d.update(kw); return ReportVersion(**d)

def test_insert_report_uses_expected_table():
    c=Cursor(); ReportRepository().insert_report(c,report())
    assert 'reporting.report_versions' in c.calls[0][0]

def test_invalid_hash_rejected():
    with pytest.raises(ValueError): ReportRepository().insert_report(Cursor(),report(report_input_hash='bad'))

def test_find_equivalent_excludes_invalid_states():
    rid=uuid4(); c=Cursor((rid,)); got=ReportRepository().find_equivalent(c,uuid4(),'PUBLIC','d'*64)
    assert got==rid
    assert "INVALIDATED" in c.calls[0][0]

def test_dependency_hash_validated():
    dep=ReportDependency(uuid4(),uuid4(),'PASSPORT','P-1','bad','1',uuid4())
    with pytest.raises(ValueError): ReportRepository().insert_dependency(Cursor(),dep)
