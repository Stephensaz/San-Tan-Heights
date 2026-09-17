from pathlib import Path
from uuid import uuid4
import pytest

from src.report_builder.deduplication import ReportDeduplicationResult
from src.report_builder.hashing import CanonicalPayloadHashEngine
from src.report_builder.persistence import ReportPersistenceService, PersistReportCommand, ReportPersistenceError
from src.report_builder.repository import ReportRepository
from src.report_builder.schema import CanonicalReportSchema
from tests.unit.report_builder.test_canonical_payload_builder import fixture

ROOT=Path(__file__).resolve().parents[3]

class Repo(ReportRepository):
    def __init__(self): self.locked=[]; self.reports=[]; self.deps=[]
    def lock_target(self,cursor,property_id,variant): self.locked.append((property_id,variant))
    def insert_report(self,cursor,report): self.reports.append(report)
    def insert_dependency(self,cursor,dep): self.deps.append(dep)

class Alloc:
    def __init__(self,value=4): self.value=value; self.calls=[]
    def allocate(self,cursor,property_id,variant): self.calls.append((property_id,variant)); return self.value

class Dedupe:
    def __init__(self,result): self.result=result; self.calls=[]
    def find(self,cursor,**kw): self.calls.append(kw); return self.result

def command():
    builder,inputs,sels,wording,glossary,manifest=fixture(); payload=builder.build(inputs=inputs,selections=sels,resolved_wording=wording,glossary=glossary,dependency_manifest=manifest)
    return PersistReportCommand(inputs.property_id,inputs.report_variant,inputs.snapshot_id,inputs.report_schema_version,inputs.content_contract_version,inputs.variant_policy_version,'0.1.19','d'*64,payload,manifest,'TEST')

def service(repo,dedupe,alloc=None):
    return ReportPersistenceService(repository=repo,allocator=alloc or Alloc(),deduplication=dedupe,payload_hasher=CanonicalPayloadHashEngine(CanonicalReportSchema.from_repository(ROOT)))

def test_equivalent_report_is_reused_before_version_allocation():
    rid=uuid4(); repo=Repo(); alloc=Alloc(); dedupe=Dedupe(ReportDeduplicationResult(True,rid,'same')); result=service(repo,dedupe,alloc).persist(object(),command())
    assert result.reused_existing and result.report_id==rid and alloc.calls==[] and repo.reports==[]

def test_new_report_allocates_version_and_persists_all_dependencies():
    repo=Repo(); alloc=Alloc(7); dedupe=Dedupe(ReportDeduplicationResult(False,None,'new')); cmd=command(); result=service(repo,dedupe,alloc).persist(object(),cmd)
    assert not result.reused_existing and result.version_number==7
    assert len(repo.reports)==1 and len(repo.deps)==len(cmd.dependency_manifest.entries)
    assert repo.reports[0].canonical_payload_hash==repo.reports[0].stored_payload_hash
    assert any(d.source_snapshot_id is None for d in repo.deps)

def test_payload_lineage_manifest_mismatch_fails_before_version_allocation():
    repo=Repo(); alloc=Alloc(); dedupe=Dedupe(ReportDeduplicationResult(False,None,'new')); cmd=command(); cmd.canonical_payload['lineage']['dependency_manifest_hash']='e'*64
    with pytest.raises(ReportPersistenceError,match='DEPENDENCY_MANIFEST'):
        service(repo,dedupe,alloc).persist(object(),cmd)
    assert alloc.calls==[] and repo.reports==[]
