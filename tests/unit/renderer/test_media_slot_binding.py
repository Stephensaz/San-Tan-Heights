from pathlib import Path
import pytest
from src.renderer.media import MediaAsset, MediaSlotBinder, MediaBindingError
ROOT=Path(__file__).resolve().parents[3]

def asset(**o):
    v=dict(media_id='m1',media_class='SUBJECT_EXTERIOR_FRONT',property_id='p1',approval_status='APPROVED',rights_status='CLEARED',semantic_fingerprint='a'*64,version='1.0.0'); v.update(o); return MediaAsset(**v)

def test_subject_media_must_match_property():
    b=MediaSlotBinder.from_repository(ROOT)
    got=b.bind(property_id='p1',slots=[{'slot_id':'hero','slot_type':'HERO_EXTERIOR','required':False}],assets=[asset(property_id='p2')])
    assert got[0].media_id is None and got[0].omitted_reason=='NO_APPROVED_COMPATIBLE_MEDIA'

def test_rights_and_approval_are_required():
    b=MediaSlotBinder.from_repository(ROOT)
    got=b.bind(property_id='p1',slots=[{'slot_id':'hero','slot_type':'HERO_EXTERIOR','required':False}],assets=[asset(rights_status='UNKNOWN')])
    assert got[0].media_id is None

def test_required_slot_fails_closed_without_media():
    b=MediaSlotBinder.from_repository(ROOT)
    with pytest.raises(MediaBindingError): b.bind(property_id='p1',slots=[{'slot_id':'hero','slot_type':'HERO_EXTERIOR','required':True}],assets=[])

def test_binding_emits_exact_media_dependency():
    b=MediaSlotBinder.from_repository(ROOT)
    got=b.bind(property_id='p1',slots=[{'slot_id':'hero','slot_type':'HERO_EXTERIOR','required':False}],assets=[asset()])[0]
    assert got.media_id=='m1'; assert got.dependency.dependency_type=='MEDIA'; assert got.dependency.slot_id=='hero'
