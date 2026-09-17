from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4
import pytest

from src.report_builder.dependencies import ReportDependencyManifestBuilder
from src.report_builder.findings import FindingSelector
from src.report_builder.glossary import GlossaryResolver
from src.report_builder.labels import FriendlyLabelRegistry
from src.report_builder.payload import CanonicalPayloadBuilder, CanonicalPayloadInputs, CanonicalPayloadBuildError
from src.report_builder.schema import CanonicalReportSchema
from src.report_builder.sections import ReportSectionRegistry
from src.report_builder.variant import VariantPolicyRegistry
from src.report_builder.wording import ApprovedWordingResolver
from src.snapshot.repository.models import SnapshotFindingRecord

ROOT=Path(__file__).resolve().parents[3]

def fixture():
    snap=uuid4(); prop=uuid4(); finding=SnapshotFindingRecord(uuid4(),snap,'f1','REAR_ADJACENCY','P1','1','a'*64,{'value':'COMMON_AREA'},'HIGH','PASS','PRODUCTION_READY','ALL','Agent rear','Seller rear','Public rear','wa','ws','wp','b'*64,'c'*64)
    variants=VariantPolicyRegistry.from_repository(ROOT); sections=ReportSectionRegistry.from_repository(ROOT); labels=FriendlyLabelRegistry.from_repository(ROOT); glossary_resolver=GlossaryResolver.from_repository(ROOT); schema=CanonicalReportSchema.from_repository(ROOT); selections=FindingSelector(variants,sections).select([finding],'PUBLIC'); wording={'f1':ApprovedWordingResolver().resolve(finding,'PUBLIC')}; glossary=glossary_resolver.resolve(selections,'PUBLIC'); p=variants.get('PUBLIC')
    manifest=ReportDependencyManifestBuilder().build(snapshot_id=snap,selections=selections,resolved_wording=wording,report_schema_version='1.0.0',content_contract_version='1.0.0',variant_policy_id=p.policy_id,variant_policy_version=p.version,section_registry_id=sections.registry_id,section_registry_version=sections.version,friendly_label_registry_id=labels.registry_id,friendly_label_version=labels.version,glossary_registry_id=glossary_resolver.registry_id,glossary_version=glossary_resolver.version)
    titles={s.section_id:s.section_id.replace('-',' ').title() for s in sections.for_variant('PUBLIC')}
    inputs=CanonicalPayloadInputs(property_id=prop,snapshot_id=snap,report_variant='PUBLIC',report_schema_version='1.0.0',content_contract_version='1.0.0',variant_policy_version=p.version,verified_through=datetime(2026,9,16,19,tzinfo=timezone.utc),property_identity={'address':'123 Example Ave','community':'San Tan Heights','phase':'C-1','builder':None,'floor_plan':None},summary_items=('Verified property intelligence.',),section_titles=titles,disclaimers=('Informational property intelligence.',),brand_profile_id='default',brand_version='1.0.0')
    return CanonicalPayloadBuilder(sections=sections,labels=labels,schema=schema),inputs,selections,wording,glossary,manifest

def test_builds_schema_valid_renderer_neutral_payload():
    builder,inputs,sels,wording,glossary,manifest=fixture(); payload=builder.build(inputs=inputs,selections=sels,resolved_wording=wording,glossary=glossary,dependency_manifest=manifest)
    assert payload['metadata']['report_variant']=='PUBLIC'
    assert payload['findings'][0]['display_text']=='Public rear'
    assert payload['findings'][0]['label']=='Rear Property Relationship'
    assert payload['lineage']['dependency_manifest_hash']==manifest.manifest_hash
    assert 'css' not in str(payload).lower()

def test_requires_governed_summary_instead_of_inventing_one():
    builder,inputs,sels,wording,glossary,manifest=fixture(); inputs=CanonicalPayloadInputs(**{**inputs.__dict__,'summary_items':()})
    with pytest.raises(CanonicalPayloadBuildError,match='summary_items'):
        builder.build(inputs=inputs,selections=sels,resolved_wording=wording,glossary=glossary,dependency_manifest=manifest)

def test_missing_approved_section_title_fails_closed():
    builder,inputs,sels,wording,glossary,manifest=fixture(); inputs=CanonicalPayloadInputs(**{**inputs.__dict__,'section_titles':{'summary':'Summary'}})
    with pytest.raises(CanonicalPayloadBuildError,match='section title'):
        builder.build(inputs=inputs,selections=sels,resolved_wording=wording,glossary=glossary,dependency_manifest=manifest)
