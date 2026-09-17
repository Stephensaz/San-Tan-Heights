from dataclasses import FrozenInstanceError

import pytest

from src.presentation import (
    PresentationAudience,
    PresentationChannel,
    PresentationPackageInput,
)


def _package(**overrides):
    values = {
        "source_report_id": "report-123",
        "source_report_version": 7,
        "audience": PresentationAudience.SELLER,
        "channel": PresentationChannel.WEB,
        "canonical_payload_hash": "a" * 64,
        "presentation_input_hash": "b" * 64,
        "render_contract_version": "1.0.0",
        "template_id": "seller-standard",
        "template_version": "1.0.0",
    }
    values.update(overrides)
    return PresentationPackageInput(**values)


def test_bootstrap_supports_locked_audiences_and_channels():
    assert {x.value for x in PresentationAudience} == {"AGENT", "SELLER", "PUBLIC"}
    assert {x.value for x in PresentationChannel} == {"WEB", "PDF", "PRINT"}


def test_package_input_is_immutable():
    package = _package()
    with pytest.raises(FrozenInstanceError):
        package.template_id = "changed"


def test_package_requires_governed_hashes():
    with pytest.raises(ValueError, match="canonical_payload_hash"):
        _package(canonical_payload_hash="not-a-hash")
    with pytest.raises(ValueError, match="presentation_input_hash"):
        _package(presentation_input_hash="C" * 64)


def test_package_is_bound_to_locked_presentation_contract():
    with pytest.raises(ValueError, match="contract id"):
        _package(presentation_contract_id="OTHER")
    with pytest.raises(ValueError, match="contract version"):
        _package(presentation_contract_version="2.0.0")


def test_target_key_is_deterministic():
    package = _package()
    assert package.target_key == "report-123:7:SELLER:WEB:seller-standard:1.0.0"
