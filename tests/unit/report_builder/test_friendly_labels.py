from pathlib import Path
import pytest
from src.report_builder.labels import FriendlyLabelRegistry, FriendlyLabelError
from src.report_builder.sections import ReportSectionRegistry

ROOT=Path(__file__).resolve().parents[3]

def test_labels_load_and_are_audience_specific():
    r=FriendlyLabelRegistry.from_repository(ROOT)
    assert r.resolve('REAR_ADJACENCY','AGENT')=='Rear Adjacency'
    assert r.resolve('REAR_ADJACENCY','SELLER')=="What's Behind the Home"
    assert r.resolve('REAR_ADJACENCY','PUBLIC')=='Rear Property Relationship'

def test_all_section_finding_types_have_labels():
    labels=FriendlyLabelRegistry.from_repository(ROOT)
    sections=ReportSectionRegistry.from_repository(ROOT)
    for section in sections.sections:
        for finding_type in section.finding_types:
            for variant in section.allowed_variants:
                assert labels.resolve(finding_type,variant)

def test_missing_label_fails_closed():
    with pytest.raises(FriendlyLabelError): FriendlyLabelRegistry.from_repository(ROOT).resolve('NO_SUCH_TERM','PUBLIC')
