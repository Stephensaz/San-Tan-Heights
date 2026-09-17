from pathlib import Path
from src.renderer.contracts import RenderContractRegistry
from src.renderer.media import MediaAsset, MediaSlotBinder
from src.renderer.diagrams import DiagramAsset, DiagramSlotBinder
from src.renderer.requests import PresentationProfile, RenderRequestService
ROOT=Path(__file__).resolve().parents[3]

def service(): return RenderRequestService(contracts=RenderContractRegistry.from_repository(ROOT),media_binder=MediaSlotBinder.from_repository(ROOT),diagram_binder=DiagramSlotBinder.from_repository(ROOT))

def profile(**o):
    v=dict(template_id='PROPERTY_REPORT',template_version='1.0.0',template_fingerprint='c'*64,brand_profile_id='STH_DEFAULT',brand_version='1.0.0',brand_fingerprint='d'*64,renderer_version='1.0.0'); v.update(o); return PresentationProfile(**v)

def build(p=None):
    return service().build(report_id='11111111-1111-1111-1111-111111111111',property_id='p1',render_type='WEB',canonical_payload_hash='a'*64,report_input_hash='b'*64,media_slots=[],diagram_slots=[],media_assets=[],diagram_assets=[],profile=p or profile())

def test_template_and_branding_are_first_class_dependencies():
    r=build(); assert [(d.dependency_type,d.dependency_id) for d in r.dependencies]==[('TEMPLATE','PROPERTY_REPORT'),('BRANDING','STH_DEFAULT')]

def test_brand_change_changes_presentation_hash_not_report_hash_input():
    a=build(); b=build(profile(brand_version='1.0.1',brand_fingerprint='e'*64))
    assert a.presentation_input_hash != b.presentation_input_hash

def test_render_request_binds_media_and_diagrams_into_hash_dependencies():
    s=service()
    m=MediaAsset('m1','SUBJECT_EXTERIOR_FRONT','p1','APPROVED','CLEARED','e'*64,'1.0.0')
    d=DiagramAsset('d1','REAR_ADJACENCY','p1','APPROVED','PASS','f'*64,'1.0.0',('f1',))
    r=s.build(report_id='11111111-1111-1111-1111-111111111111',property_id='p1',render_type='PDF',canonical_payload_hash='a'*64,report_input_hash='b'*64,media_slots=[{'slot_id':'hero','slot_type':'HERO_EXTERIOR','required':False}],diagram_slots=[{'slot_id':'rear','diagram_type':'REAR_ADJACENCY','required':False,'finding_ids':['f1']}],media_assets=[m],diagram_assets=[d],profile=profile())
    assert {x.dependency_type for x in r.dependencies}=={'TEMPLATE','BRANDING','MEDIA','DIAGRAM'}
