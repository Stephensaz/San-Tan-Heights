from pathlib import Path

import pytest

from src.presentation.audience import AudiencePresentationPolicies
from src.presentation.package import PresentationAudience

ROOT = Path(__file__).resolve().parents[3]


def test_audience_policies_load_from_existing_report_variant_registry():
    policies = AudiencePresentationPolicies.from_repository(ROOT)
    agent = policies.for_audience(PresentationAudience.AGENT)
    seller = policies.for_audience(PresentationAudience.SELLER)
    public = policies.for_audience(PresentationAudience.PUBLIC)
    assert agent.evidence_depth == "DETAILED"
    assert seller.evidence_depth == "STANDARD"
    assert public.evidence_depth == "LIGHT"
    assert agent.confidence_visibility == "DETAILED"
    assert seller.confidence_visibility == "FRIENDLY"
    assert public.confidence_visibility == "SELECTIVE"


def test_public_cannot_present_seller_or_agent_internal_classification():
    policies = AudiencePresentationPolicies.from_repository(ROOT)
    public = policies.for_audience(PresentationAudience.PUBLIC)
    assert public.allows(classification="PUBLIC_DATA", publication_scope="PUBLIC")
    assert not public.allows(classification="SELLER_DATA", publication_scope="PUBLIC")
    assert not public.allows(classification="AGENT_INTERNAL", publication_scope="PUBLIC")


def test_seller_cannot_present_agent_internal_content():
    policies = AudiencePresentationPolicies.from_repository(ROOT)
    seller = policies.for_audience(PresentationAudience.SELLER)
    with pytest.raises(ValueError):
        seller.require_allowed(classification="AGENT_INTERNAL", publication_scope="SELLER")


def test_agent_can_present_agent_internal_content_with_agent_scope():
    policies = AudiencePresentationPolicies.from_repository(ROOT)
    agent = policies.for_audience(PresentationAudience.AGENT)
    agent.require_allowed(classification="AGENT_INTERNAL", publication_scope="AGENT")


def test_policy_mapping_is_read_only():
    policies = AudiencePresentationPolicies.from_repository(ROOT)
    with pytest.raises(TypeError):
        policies.policies[PresentationAudience.PUBLIC] = policies.for_audience(PresentationAudience.AGENT)
