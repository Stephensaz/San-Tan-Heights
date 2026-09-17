from pathlib import Path
import pytest
from src.renderer.diagrams import DiagramAsset, DiagramSlotBinder, DiagramBindingError
ROOT=Path(__file__).resolve().parents[3]

def asset(**o):
    v=dict(diagram_id='d1',diagram_type='REAR_ADJACENCY',property_id='p1',approval_status='APPROVED',qa_status='PASS',semantic_fingerprint='b'*64,version='1.0.0',finding_ids=('f1',)); v.update(o); return DiagramAsset(**v)

def slot(required=False): return {'slot_id':'rear','diagram_type':'REAR_ADJACENCY','required':required,'finding_ids':['f1']}

def test_diagram_requires_property_and_finding_lineage_match():
    b=DiagramSlotBinder.from_repository(ROOT)
    assert b.bind(property_id='p1',slots=[slot()],assets=[asset(property_id='p2')])[0].diagram_id is None
    assert b.bind(property_id='p1',slots=[slot()],assets=[asset(finding_ids=('f2',))])[0].diagram_id is None

def test_diagram_requires_approved_pass_qa():
    b=DiagramSlotBinder.from_repository(ROOT)
    assert b.bind(property_id='p1',slots=[slot()],assets=[asset(qa_status='REVIEW_REQUIRED')])[0].diagram_id is None

def test_required_diagram_fails_closed():
    b=DiagramSlotBinder.from_repository(ROOT)
    with pytest.raises(DiagramBindingError): b.bind(property_id='p1',slots=[slot(True)],assets=[])

def test_binding_emits_exact_diagram_dependency():
    b=DiagramSlotBinder.from_repository(ROOT)
    x=b.bind(property_id='p1',slots=[slot()],assets=[asset()])[0]
    assert x.diagram_id=='d1'; assert x.dependency.dependency_type=='DIAGRAM'; assert x.dependency.slot_id=='rear'
