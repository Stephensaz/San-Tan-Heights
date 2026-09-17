from copy import deepcopy
from pathlib import Path
from uuid import uuid4

from src.report_builder.hashing import CanonicalPayloadHashEngine
from src.report_builder.schema import CanonicalReportSchema
from tests.unit.report_builder.test_canonical_payload_builder import fixture

ROOT=Path(__file__).resolve().parents[3]

def payload():
    builder,inputs,sels,wording,glossary,manifest=fixture()
    return builder.build(inputs=inputs,selections=sels,resolved_wording=wording,glossary=glossary,dependency_manifest=manifest)

def test_payload_hash_is_deterministic_for_equivalent_object_order():
    engine=CanonicalPayloadHashEngine(CanonicalReportSchema.from_repository(ROOT)); a=payload()
    b={k:a[k] for k in reversed(list(a.keys()))}
    assert engine.calculate(a).canonical_payload_hash==engine.calculate(b).canonical_payload_hash

def test_exact_lineage_change_changes_payload_hash():
    engine=CanonicalPayloadHashEngine(CanonicalReportSchema.from_repository(ROOT)); a=payload(); b=deepcopy(a)
    sid=str(uuid4()); b['metadata']['snapshot_id']=sid; b['lineage']['snapshot_id']=sid
    assert engine.calculate(a).canonical_payload_hash!=engine.calculate(b).canonical_payload_hash

def test_verify_detects_payload_drift():
    engine=CanonicalPayloadHashEngine(CanonicalReportSchema.from_repository(ROOT)); a=payload(); h=engine.calculate(a).canonical_payload_hash
    a['summary'][0]='Changed governed summary.'
    import pytest
    with pytest.raises(ValueError,match='HASH_MISMATCH'): engine.verify(a,h)
