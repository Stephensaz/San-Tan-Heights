from pathlib import Path
from uuid import uuid4
import pytest
from src.report_builder.glossary import GlossaryResolver, GlossaryError
from src.report_builder.findings import FindingSelection
from src.snapshot.repository.models import SnapshotFindingRecord

ROOT=Path(__file__).resolve().parents[3]

def sel(ftype):
    f=SnapshotFindingRecord(uuid4(),uuid4(),'f-'+ftype,ftype,'P1','1','a'*64,{},'HIGH','PASS','PRODUCTION_READY','ALL','A','S','P','a1','s1','p1','b'*64,'c'*64)
    return FindingSelection(f,'lot-location','PUBLIC_DATA')

def test_universal_terms_always_present():
    terms=GlossaryResolver.from_repository(ROOT).resolve([], 'PUBLIC')
    ids={x.term_id for x in terms}
    assert {'VERIFIED','DATA_FRESHNESS'} <= ids

def test_contextual_term_included_when_related_finding_used():
    terms=GlossaryResolver.from_repository(ROOT).resolve([sel('CANONICAL_PHASE')], 'SELLER')
    by={x.term_id:x for x in terms}
    assert by['RECORDED_PHASE'].label=='Community Phase'

def test_unrelated_term_omitted():
    ids={x.term_id for x in GlossaryResolver.from_repository(ROOT).resolve([sel('CANONICAL_PHASE')],'PUBLIC')}
    assert 'COMMON_AREA' not in ids

def test_common_area_definition_preserves_limitation():
    terms=GlossaryResolver.from_repository(ROOT).resolve([sel('REAR_ADJACENCY')],'PUBLIC')
    common=next(x for x in terms if x.term_id=='COMMON_AREA')
    assert 'does not by itself guarantee' in common.definition

def test_unknown_variant_fails_closed():
    with pytest.raises(GlossaryError): GlossaryResolver.from_repository(ROOT).resolve([], 'OPS')
