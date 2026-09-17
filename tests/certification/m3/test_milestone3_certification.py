from copy import deepcopy
from pathlib import Path
from src.report_builder.diff import ReportSemanticDiffEngine
from src.report_builder.hashing import CanonicalPayloadHashEngine
from src.report_builder.schema import CanonicalReportSchema
from tests.unit.report_builder.test_canonical_payload_builder import fixture
ROOT=Path(__file__).resolve().parents[3]

def test_m3_report_production_certification_contract():
    b,i,s,w,g,m=fixture(); p=b.build(inputs=i,selections=s,resolved_wording=w,glossary=g,dependency_manifest=m)
    hasher=CanonicalPayloadHashEngine(CanonicalReportSchema.from_repository(ROOT)); h=hasher.calculate(p)
    assert hasher.verify(p,h.canonical_payload_hash).canonical_payload_hash==h.canonical_payload_hash
    lineage=deepcopy(p); lineage['metadata']['snapshot_id']='00000000-0000-0000-0000-000000000001'; lineage['lineage']['snapshot_id']=lineage['metadata']['snapshot_id']; lineage['findings'][0]['source_snapshot_id']=lineage['metadata']['snapshot_id']
    assert not ReportSemanticDiffEngine().compare(p,lineage).changed
    sql=(ROOT/'database/migrations/0035_ready_semantic_immutability.sql').read_text()
    assert 'READY_REPORT_SEMANTICS_IMMUTABLE' in sql and 'READY_REPORT_DEPENDENCIES_IMMUTABLE' in sql
    worker=(ROOT/'workers/regeneration_worker/worker.py').read_text()
    assert 'publication' not in worker.lower()
