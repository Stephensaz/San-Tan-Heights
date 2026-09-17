from uuid import uuid4
import pytest
from src.report_builder.wording import ApprovedWordingResolver, ApprovedWordingError
from src.snapshot.repository.models import SnapshotFindingRecord

def f(**kw):
    d=dict(snapshot_finding_id=uuid4(),snapshot_id=uuid4(),finding_id='f1',finding_type='REAR_ADJACENCY',passport_id='P1',passport_version='1',passport_semantic_fingerprint='a'*64,canonical_value={'x':1},confidence_code='HIGH',qa_status='PASS',production_status='PRODUCTION_READY',publication_scope='ALL',agent_wording='Exact agent',seller_wording='Exact seller',public_wording='Exact public',agent_wording_version='a1',seller_wording_version='s1',public_wording_version='p1',semantic_fingerprint='b'*64,evidence_reference_set_hash='c'*64)
    d.update(kw); return SnapshotFindingRecord(**d)

def test_resolves_exact_public_wording_and_version():
    got=ApprovedWordingResolver().resolve(f(),'PUBLIC')
    assert got.text=='Exact public' and got.version=='p1'

def test_missing_wording_blocks_instead_of_fallback():
    with pytest.raises(ApprovedWordingError, match='missing approved PUBLIC wording'):
        ApprovedWordingResolver().resolve(f(public_wording=None),'PUBLIC')

def test_missing_wording_version_blocks():
    with pytest.raises(ApprovedWordingError, match='wording version'):
        ApprovedWordingResolver().resolve(f(public_wording_version=None),'PUBLIC')

def test_wrong_tier_never_substituted():
    with pytest.raises(ApprovedWordingError):
        ApprovedWordingResolver().resolve(f(public_wording=None,agent_wording='Agent substitute'),'PUBLIC')

def test_unknown_variant_fails_closed():
    with pytest.raises(ApprovedWordingError): ApprovedWordingResolver().resolve(f(),'OPS')
