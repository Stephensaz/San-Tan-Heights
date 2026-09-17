from dataclasses import replace
from pathlib import Path
from uuid import uuid4

from src.report_builder.hashing import CanonicalPayloadHashEngine
from src.report_builder.repository import ReportVersion
from src.report_builder.schema import CanonicalReportSchema
from src.report_builder.validation import ReportValidationEngine
from tests.unit.report_builder.test_canonical_payload_builder import fixture

ROOT=Path(__file__).resolve().parents[3]

def built_report():
    builder,inputs,sels,wording,glossary,manifest=fixture(); payload=builder.build(inputs=inputs,selections=sels,resolved_wording=wording,glossary=glossary,dependency_manifest=manifest)
    schema=CanonicalReportSchema.from_repository(ROOT); hasher=CanonicalPayloadHashEngine(schema); h=hasher.calculate(payload).canonical_payload_hash
    report=ReportVersion(uuid4(),inputs.property_id,'PUBLIC',1,inputs.snapshot_id,inputs.report_schema_version,inputs.content_contract_version,inputs.variant_policy_version,'0.1.19','d'*64,h,payload,manifest.manifest_hash,'TEST',stored_payload_hash=h)
    return schema,hasher,report,manifest

def test_valid_report_passes_semantic_gate():
    schema,hasher,report,manifest=built_report(); result=ReportValidationEngine(schema=schema,payload_hasher=hasher).validate(report=report,dependency_manifest=manifest)
    assert result.valid and result.issues==()

def test_hash_drift_fails_validation():
    schema,hasher,report,manifest=built_report(); payload=dict(report.canonical_payload); payload['summary']=['Changed summary']; report=replace(report,canonical_payload=payload)
    result=ReportValidationEngine(schema=schema,payload_hasher=hasher).validate(report=report,dependency_manifest=manifest)
    assert not result.valid and any(x.code=='CANONICAL_PAYLOAD_HASH_MISMATCH' for x in result.issues)

def test_publication_eligible_requires_ready_clean_pass():
    schema,hasher,report,manifest=built_report(); report=replace(report,publication_eligible=True,content_state='BUILDING',qa_status='PENDING')
    result=ReportValidationEngine(schema=schema,payload_hasher=hasher).validate(report=report,dependency_manifest=manifest)
    assert any(x.code=='PUBLICATION_ELIGIBILITY_STATE_INVALID' for x in result.issues)

def test_wrong_dependency_manifest_fails():
    schema,hasher,report,manifest=built_report(); report=replace(report,dependency_manifest_hash='f'*64)
    result=ReportValidationEngine(schema=schema,payload_hasher=hasher).validate(report=report,dependency_manifest=manifest)
    codes={x.code for x in result.issues}
    assert 'REPORT_DEPENDENCY_HASH_MISMATCH' in codes and 'DEPENDENCY_MANIFEST_HASH_MISMATCH' in codes
