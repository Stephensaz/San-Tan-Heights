from pathlib import Path
from uuid import uuid4
import pytest

from src.report_builder.dependencies import ReportDependencyManifestBuilder, ReportDependencyManifestError
from src.report_builder.findings import FindingSelector
from src.report_builder.sections import ReportSectionRegistry
from src.report_builder.variant import VariantPolicyRegistry
from src.report_builder.wording import ApprovedWordingResolver
from src.report_builder.labels import FriendlyLabelRegistry
from src.report_builder.glossary import GlossaryResolver
from src.snapshot.repository.models import SnapshotFindingRecord

ROOT=Path(__file__).resolve().parents[3]

def finding(fid='f1', semantic='b'*64, passport='a'*64):
    return SnapshotFindingRecord(uuid4(),uuid4(),fid,'REAR_ADJACENCY','P1','1',passport,{'value':'COMMON_AREA'},'HIGH','PASS','PRODUCTION_READY','ALL',
        'Agent text','Seller text','Public text','wa','ws','wp',semantic,'c'*64)

def components():
    variants=VariantPolicyRegistry.from_repository(ROOT); sections=ReportSectionRegistry.from_repository(ROOT)
    return variants, sections, FriendlyLabelRegistry.from_repository(ROOT), GlossaryResolver.from_repository(ROOT)

def test_manifest_contains_only_consumed_finding_and_governance_dependencies():
    variants,sections,labels,glossary=components(); f=finding(); selections=FindingSelector(variants,sections).select([f],'PUBLIC')
    wording={f.finding_id:ApprovedWordingResolver().resolve(f,'PUBLIC')}
    policy=variants.get('PUBLIC')
    manifest=ReportDependencyManifestBuilder().build(snapshot_id=f.snapshot_id,selections=selections,resolved_wording=wording,
        report_schema_version='1.0.0',content_contract_version='1.0.0',variant_policy_id=policy.policy_id,variant_policy_version=policy.version,
        section_registry_id=sections.registry_id,section_registry_version=sections.version,friendly_label_registry_id=labels.registry_id,
        friendly_label_version=labels.version,glossary_registry_id=glossary.registry_id,glossary_version=glossary.version)
    types={x.dependency_type for x in manifest.entries}
    assert {'PRODUCTION_FINDING','PASSPORT','APPROVED_WORDING','REPORT_SCHEMA','CONTENT_CONTRACT','VARIANT_POLICY','REPORT_SECTIONS','FRIENDLY_LABELS','GLOSSARY'} <= types
    assert len(manifest.manifest_hash)==64

def test_manifest_hash_ignores_snapshot_id_when_semantics_same():
    variants,sections,labels,glossary=components(); f=finding(); sels=FindingSelector(variants,sections).select([f],'PUBLIC'); wr={f.finding_id:ApprovedWordingResolver().resolve(f,'PUBLIC')}; p=variants.get('PUBLIC')
    kw=dict(selections=sels,resolved_wording=wr,report_schema_version='1',content_contract_version='1',variant_policy_id=p.policy_id,variant_policy_version=p.version,section_registry_id=sections.registry_id,section_registry_version=sections.version,friendly_label_registry_id=labels.registry_id,friendly_label_version=labels.version,glossary_registry_id=glossary.registry_id,glossary_version=glossary.version)
    a=ReportDependencyManifestBuilder().build(snapshot_id=uuid4(),**kw); b=ReportDependencyManifestBuilder().build(snapshot_id=uuid4(),**kw)
    assert a.manifest_hash==b.manifest_hash

def test_missing_wording_dependency_fails_closed():
    variants,sections,labels,glossary=components(); f=finding(); sels=FindingSelector(variants,sections).select([f],'PUBLIC'); p=variants.get('PUBLIC')
    with pytest.raises(ReportDependencyManifestError,match='missing resolved wording'):
        ReportDependencyManifestBuilder().build(snapshot_id=f.snapshot_id,selections=sels,resolved_wording={},report_schema_version='1',content_contract_version='1',variant_policy_id=p.policy_id,variant_policy_version=p.version,section_registry_id=sections.registry_id,section_registry_version=sections.version,friendly_label_registry_id=labels.registry_id,friendly_label_version=labels.version,glossary_registry_id=glossary.registry_id,glossary_version=glossary.version)
