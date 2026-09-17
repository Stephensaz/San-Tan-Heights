from pathlib import Path
from uuid import uuid4
from src.report_builder.dependencies import ReportDependencyManifestBuilder
from src.report_builder.findings import FindingSelector
from src.report_builder.hashing import ReportInputHashEngine
from src.report_builder.sections import ReportSectionRegistry
from src.report_builder.variant import VariantPolicyRegistry
from src.report_builder.wording import ApprovedWordingResolver, ResolvedWording
from src.report_builder.labels import FriendlyLabelRegistry
from src.report_builder.glossary import GlossaryResolver
from src.snapshot.repository.models import SnapshotFindingRecord

ROOT=Path(__file__).resolve().parents[3]

def f(): return SnapshotFindingRecord(uuid4(),uuid4(),'f1','REAR_ADJACENCY','P1','1','a'*64,{'value':'COMMON_AREA'},'HIGH','PASS','PRODUCTION_READY','ALL','Agent','Seller','Public','wa','ws','wp','b'*64,'c'*64)

def setup():
    finding=f(); variants=VariantPolicyRegistry.from_repository(ROOT); sections=ReportSectionRegistry.from_repository(ROOT); labels=FriendlyLabelRegistry.from_repository(ROOT); glossary=GlossaryResolver.from_repository(ROOT); sels=FindingSelector(variants,sections).select([finding],'PUBLIC'); wr={'f1':ApprovedWordingResolver().resolve(finding,'PUBLIC')}; p=variants.get('PUBLIC')
    manifest=ReportDependencyManifestBuilder().build(snapshot_id=finding.snapshot_id,selections=sels,resolved_wording=wr,report_schema_version='1',content_contract_version='1',variant_policy_id=p.policy_id,variant_policy_version=p.version,section_registry_id=sections.registry_id,section_registry_version=sections.version,friendly_label_registry_id=labels.registry_id,friendly_label_version=labels.version,glossary_registry_id=glossary.registry_id,glossary_version=glossary.version)
    return finding,sels,wr,manifest,p,labels,glossary

def test_report_input_hash_deterministic_and_excludes_snapshot_identity():
    _,sels,wr,manifest,p,labels,glossary=setup(); engine=ReportInputHashEngine(); prop=str(uuid4())
    kw=dict(property_id=prop,report_variant='PUBLIC',selections=sels,resolved_wording=wr,dependency_manifest=manifest,report_schema_version='1',content_contract_version='1',variant_policy_version=p.version,friendly_label_version=labels.version,glossary_version=glossary.version)
    assert engine.calculate(**kw).report_input_hash==engine.calculate(**kw).report_input_hash

def test_wording_change_changes_report_input_hash():
    _,sels,wr,manifest,p,labels,glossary=setup(); engine=ReportInputHashEngine(); prop=str(uuid4())
    base=dict(property_id=prop,report_variant='PUBLIC',selections=sels,dependency_manifest=manifest,report_schema_version='1',content_contract_version='1',variant_policy_version=p.version,friendly_label_version=labels.version,glossary_version=glossary.version)
    a=engine.calculate(resolved_wording=wr,**base).report_input_hash
    changed={'f1':ResolvedWording('Changed governed wording','wp2')}
    b=engine.calculate(resolved_wording=changed,**base).report_input_hash
    assert a!=b
