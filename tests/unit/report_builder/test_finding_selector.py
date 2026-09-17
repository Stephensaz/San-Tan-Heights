from pathlib import Path
from uuid import uuid4
import pytest
from src.report_builder.findings import FindingSelector, FindingSelectionError
from src.report_builder.variant import VariantPolicyRegistry
from src.report_builder.sections import ReportSectionRegistry
from src.snapshot.repository.models import SnapshotFindingRecord

ROOT=Path(__file__).resolve().parents[3]

def f(scope='ALL', finding_type='REAR_ADJACENCY', fid='f1', qa='PASS', status='PRODUCTION_READY'):
    return SnapshotFindingRecord(uuid4(),uuid4(),fid,finding_type,'P1','1','a'*64,{'value':'COMMON_AREA'},'HIGH',qa,status,scope,
        'Agent text','Seller text','Public text','wa','ws','wp','b'*64,'c'*64)

def selector():
    return FindingSelector(VariantPolicyRegistry.from_repository(ROOT), ReportSectionRegistry.from_repository(ROOT))

def test_public_selects_public_finding_and_maps_section():
    out=selector().select([f('PUBLIC')],'PUBLIC')
    assert len(out)==1
    assert out[0].section_id=='lot-location'
    assert out[0].classification=='PUBLIC_DATA'

def test_public_excludes_agent_only():
    assert selector().select([f('AGENT')],'PUBLIC') == ()

def test_seller_accepts_seller_scope_but_public_does_not():
    finding=f('SELLER')
    assert len(selector().select([finding],'SELLER'))==1
    assert selector().select([finding],'PUBLIC')==()

def test_non_production_or_non_pass_findings_not_consumed():
    assert selector().select([f(qa='FAIL')],'AGENT')==()
    assert selector().select([f(status='BLOCKED')],'AGENT')==()

def test_unmapped_governed_finding_is_not_invented_into_section():
    assert selector().select([f(finding_type='UNUSED_GOVERNED_FACT')],'AGENT')==()

def test_duplicate_finding_id_fails_closed():
    with pytest.raises(FindingSelectionError, match='duplicate finding_id'):
        selector().select([f(fid='same'),f(fid='same')],'AGENT')

def test_builder_identity_uses_first_governed_section_order():
    out=selector().select([f(finding_type='BUILDER_IDENTITY')],'PUBLIC')
    assert out[0].section_id=='property-identity'
