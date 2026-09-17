from pathlib import Path
from uuid import uuid4
import pytest
from src.report_builder.schema import CanonicalReportSchema, CanonicalReportSchemaError

ROOT=Path(__file__).resolve().parents[3]

def payload():
    prop=str(uuid4()); snap=str(uuid4()); h='a'*64
    return {
      'metadata': {'report_schema_version':'1.0.0','content_contract_version':'1.0.0','variant_policy_version':'1.0.0','report_variant':'PUBLIC','property_id':prop,'snapshot_id':snap,'verified_through':'2026-09-16T19:00:00Z','market_data_through':None,'builder_data_through':None},
      'property_identity': {'property_id':prop,'address':'123 Example Ave','community':'San Tan Heights','phase':'C-1','builder':None,'floor_plan':None},
      'summary':['Verified property identity'],
      'sections':[{'section_id':'summary','title':'Summary','order':1,'card_ids':['c1'],'summary':None},{'section_id':'property-identity','title':'Property Identity','order':2,'card_ids':[],'summary':None}],
      'findings':[{'finding_id':'f1','finding_type':'PROPERTY_IDENTITY','label':'Property','display_text':'123 Example Ave','section_id':'property-identity','status_label':'Verified','confidence_label':None,'limitation':None,'source_snapshot_id':snap,'semantic_fingerprint':'b'*64}],
      'cards':[{'card_id':'c1','card_type':'SUMMARY_CARD','section_id':'summary','title':'Summary','body':'Verified property identity','finding_ids':['f1'],'status_label':None}],
      'media_slots':[], 'diagram_slots':[], 'glossary':[], 'evidence_disclosures':[], 'disclaimers':['Informational property intelligence.'],
      'branding_reference': {'brand_profile_id':'default','brand_version':'1.0.0'},
      'lineage': {'snapshot_id':snap,'dependency_manifest_hash':h}
    }

def test_valid_canonical_payload():
    CanonicalReportSchema.from_repository(ROOT).validate(payload())

def test_rejects_renderer_specific_fields():
    p=payload(); p['cards'][0]['style']='display:none'
    with pytest.raises(CanonicalReportSchemaError, match='presentation-only'):
        CanonicalReportSchema.from_repository(ROOT).validate(p)

def test_rejects_property_identity_mismatch():
    p=payload(); p['property_identity']['property_id']=str(uuid4())
    with pytest.raises(CanonicalReportSchemaError, match='property identity'):
        CanonicalReportSchema.from_repository(ROOT).validate(p)

def test_rejects_unknown_card_finding_reference():
    p=payload(); p['cards'][0]['finding_ids']=['missing']
    with pytest.raises(CanonicalReportSchemaError, match='unknown findings'):
        CanonicalReportSchema.from_repository(ROOT).validate(p)
