from copy import deepcopy
from src.report_builder.diff import ReportSemanticDiffEngine
from tests.unit.report_builder.test_canonical_payload_builder import fixture

def payload():
    b,i,s,w,g,m=fixture(); return b.build(inputs=i,selections=s,resolved_wording=w,glossary=g,dependency_manifest=m)

def test_lineage_only_change_is_not_semantic_change():
    a=payload(); b=deepcopy(a); b['metadata']['snapshot_id']='00000000-0000-0000-0000-000000000001'; b['metadata']['verified_through']='2026-09-17T00:00:00Z'; b['lineage']['snapshot_id']=b['metadata']['snapshot_id']; b['lineage']['dependency_manifest_hash']='f'*64; b['findings'][0]['source_snapshot_id']=b['metadata']['snapshot_id']
    d=ReportSemanticDiffEngine().compare(a,b)
    assert not d.changed and d.changed_paths==()

def test_wording_change_is_semantic_and_deterministic():
    a=payload(); b=deepcopy(a); b['findings'][0]['display_text']='Changed governed wording'; b['cards'][1]['body']='Changed governed wording'
    e=ReportSemanticDiffEngine(); d1=e.compare(a,b); d2=e.compare(a,b)
    assert d1.changed and 'FINDING' in d1.categories and 'CARD' in d1.categories
    assert d1.diff_hash==d2.diff_hash
