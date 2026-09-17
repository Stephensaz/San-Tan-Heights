from pathlib import Path

from src.presentation.glossary import ConsumerGlossaryUi
from src.presentation.package import PresentationAudience
from src.report_builder.glossary.resolver import GlossaryResolver

ROOT = Path(__file__).resolve().parents[3]


def resolver():
    return GlossaryResolver.from_repository(ROOT)


def test_consumer_glossary_uses_governed_universal_terms():
    panel = ConsumerGlossaryUi().build(resolver(), (), PresentationAudience.PUBLIC)
    assert panel.title == "Glossary"
    assert panel.source_registry_id == "STH-CONSUMER-GLOSSARY-v1.0"
    assert tuple(item.term_id for item in panel.items) == ("DATA_FRESHNESS", "VERIFIED")


def test_consumer_glossary_uses_audience_specific_governed_definition():
    agent = ConsumerGlossaryUi().build(resolver(), (), PresentationAudience.AGENT)
    public = ConsumerGlossaryUi().build(resolver(), (), PresentationAudience.PUBLIC)
    agent_verified = next(item for item in agent.items if item.term_id == "VERIFIED")
    public_verified = next(item for item in public.items if item.term_id == "VERIFIED")
    assert "production QA" in agent_verified.definition
    assert "production QA" not in public_verified.definition
    assert agent_verified.definition != public_verified.definition


def test_consumer_glossary_preserves_source_version_and_nonblank_text():
    panel = ConsumerGlossaryUi().build(resolver(), (), PresentationAudience.SELLER)
    assert all(item.glossary_version == "1.0.0" for item in panel.items)
    assert all(item.label.strip() and item.definition.strip() for item in panel.items)


def test_consumer_glossary_is_deterministic():
    first = ConsumerGlossaryUi().build(resolver(), (), PresentationAudience.PUBLIC)
    second = ConsumerGlossaryUi().build(resolver(), (), PresentationAudience.PUBLIC)
    assert first.fingerprint == second.fingerprint
    assert len(first.fingerprint) == 64
