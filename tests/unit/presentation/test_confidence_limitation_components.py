from pathlib import Path

import pytest

from src.presentation.audience import AudiencePresentationPolicies
from src.presentation.evidence import (
    ConfidenceLimitationBuilder,
    EvidenceDisclosureItem,
    EvidenceDisclosureSet,
)
from src.presentation.package import PresentationAudience

ROOT = Path(__file__).resolve().parents[3]


def builder():
    return ConfidenceLimitationBuilder(AudiencePresentationPolicies.from_repository(ROOT))


def disclosure(audience: str, *, confidence: str | None, limitation: str | None):
    return EvidenceDisclosureSet(
        audience=audience,
        evidence_depth={"AGENT": "DETAILED", "SELLER": "STANDARD", "PUBLIC": "LIGHT"}[audience],
        items=(
            EvidenceDisclosureItem(
                finding_id="finding-1",
                label="Community Phase",
                status_label="Verified",
                confidence_label=confidence,
                limitation=limitation,
                source_snapshot_id="snapshot-1" if audience == "AGENT" else None,
                semantic_fingerprint=("a" * 64) if audience == "AGENT" else None,
            ),
        ),
        disclaimers=(),
    )


def test_agent_confidence_component_uses_detailed_mode_without_rewriting_text():
    source = disclosure("AGENT", confidence="High confidence", limitation="Based on governed recorded evidence.")
    result = builder().build(source, audience=PresentationAudience.AGENT)
    assert result.visibility_mode == "DETAILED"
    assert result.items[0].confidence_text == "High confidence"
    assert result.items[0].limitation_text == "Based on governed recorded evidence."


def test_seller_confidence_component_uses_friendly_mode():
    source = disclosure("SELLER", confidence="Verified from available records", limitation=None)
    result = builder().build(source, audience=PresentationAudience.SELLER)
    assert result.visibility_mode == "FRIENDLY"
    assert result.items[0].confidence_text == "Verified from available records"


def test_public_confidence_component_is_selective_and_does_not_invent_missing_text():
    source = disclosure("PUBLIC", confidence=None, limitation="Based on available governed records.")
    result = builder().build(source, audience=PresentationAudience.PUBLIC)
    assert result.visibility_mode == "SELECTIVE"
    assert result.items[0].confidence_text is None
    assert result.items[0].limitation_text == "Based on available governed records."


def test_component_omits_findings_with_no_confidence_or_limitation_content():
    source = disclosure("PUBLIC", confidence=None, limitation=None)
    result = builder().build(source, audience=PresentationAudience.PUBLIC)
    assert result.items == ()


def test_component_rejects_audience_mismatch():
    with pytest.raises(ValueError, match="audience mismatch"):
        builder().build(
            disclosure("SELLER", confidence="Verified from available records", limitation=None),
            audience=PresentationAudience.PUBLIC,
        )


def test_component_rejects_blank_optional_text_instead_of_normalizing_it():
    source = disclosure("SELLER", confidence=" ", limitation=None)
    with pytest.raises(ValueError, match="cannot be blank"):
        builder().build(source, audience=PresentationAudience.SELLER)


def test_confidence_limitation_fingerprint_is_deterministic():
    source = disclosure("AGENT", confidence="High confidence", limitation="Known limitation.")
    first = builder().build(source, audience=PresentationAudience.AGENT)
    second = builder().build(source, audience=PresentationAudience.AGENT)
    assert first.fingerprint == second.fingerprint
    assert len(first.fingerprint) == 64
