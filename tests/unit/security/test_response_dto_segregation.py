from copy import deepcopy
from uuid import uuid4
from src.security.responses import AudienceResponseProjector, PublicReportResponse, SellerReportResponse, AgentReportResponse

def payload(variant):
    pid=str(uuid4()); sid=str(uuid4())
    return {
      'metadata': {'report_schema_version':'1','content_contract_version':'1','variant_policy_version':'1','report_variant':variant,'property_id':pid,'snapshot_id':sid,'verified_through':'2026-09-16T00:00:00Z','market_data_through':'2026-09-15T00:00:00Z','builder_data_through':None},
      'property_identity': {'property_id':pid,'address':'123 Test St','community':'San Tan Heights','phase':'C-1','builder':None,'floor_plan':None},
      'summary':['Verified summary'], 'sections':[], 'cards':[],
      'findings':[{'finding_id':'f1','finding_type':'CORNER_STATUS','label':'Corner','display_text':'Verified corner status.','section_id':'lot-location','status_label':None,'confidence_label':'High','limitation':'Recorded sources only.','source_snapshot_id':sid,'semantic_fingerprint':'a'*64}],
      'media_slots':[], 'diagram_slots':[], 'glossary':[],
      'evidence_disclosures':[{'disclosure_id':'d1','finding_id':'f1','source_category':'COUNTY_GIS','verified_at':'2026-09-16T00:00:00Z','limitation':None,'detail':'agent-only source detail'}],
      'disclaimers':['Informational only.'], 'branding_reference':{'brand_profile_id':'b','brand_version':'1'},
      'lineage': {'snapshot_id':sid,'dependency_manifest_hash':'b'*64},
      'internal_notes':'must never serialize', 'restricted_value':'secret'
    }

def test_dtos_are_physically_distinct_and_whitelisted():
    p=AudienceResponseProjector()
    public=p.public(payload('PUBLIC')); seller=p.seller(payload('SELLER')); agent=p.agent(payload('AGENT'))
    assert isinstance(public,PublicReportResponse); assert isinstance(seller,SellerReportResponse); assert isinstance(agent,AgentReportResponse)
    assert 'lineage' not in public.to_dict() and 'evidence_disclosures' not in public.to_dict()
    assert 'lineage' not in seller.to_dict() and 'snapshot_id' not in seller.to_dict()
    assert 'lineage' in agent.to_dict() and 'snapshot_id' in agent.to_dict()

def test_seller_evidence_drops_detail_and_finding_lineage():
    seller=AudienceResponseProjector().seller(payload('SELLER')).to_dict()
    assert 'detail' not in seller['evidence_disclosures'][0]
    assert 'semantic_fingerprint' not in seller['findings'][0]
    assert 'source_snapshot_id' not in seller['findings'][0]
