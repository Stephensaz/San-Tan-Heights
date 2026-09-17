from pathlib import Path
import pytest
from src.report_builder.sections import ReportSectionRegistry, ReportSectionRegistryError

ROOT=Path(__file__).resolve().parents[3]

def test_sections_load_in_stable_order():
    r=ReportSectionRegistry.from_repository(ROOT)
    ids=[s.section_id for s in r.sections]
    assert ids == ['summary','property-identity','lot-location','home-dna','market-context','evidence','changes','freshness','glossary']

def test_required_shared_sections_are_required_for_public():
    r=ReportSectionRegistry.from_repository(ROOT)
    public={s.section_id:s for s in r.for_variant('PUBLIC')}
    assert 'PUBLIC' in public['summary'].required_by_variant
    assert 'PUBLIC' in public['evidence'].required_by_variant
    assert 'PUBLIC' in public['freshness'].required_by_variant

def test_optional_market_context_is_not_required():
    r=ReportSectionRegistry.from_repository(ROOT)
    assert not r.get('market-context').required_by_variant
    assert r.get('market-context').fallback_behavior == 'OMIT_IF_EMPTY'

def test_unknown_variant_fails_closed():
    with pytest.raises(ReportSectionRegistryError):
        ReportSectionRegistry.from_repository(ROOT).for_variant('OPS')
