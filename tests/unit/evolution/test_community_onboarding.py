import pytest

from src.evolution.community_onboarding import (
    CommunityOnboardingInput,
    assert_no_protected_defaults,
    generate_bootstrap,
    load_onboarding_contract,
)

C = "contracts/evolution/STH-COMMUNITY-ONBOARDING-v1.0.yaml"


def contract():
    return load_onboarding_contract(C)


def valid_input(**overrides):
    data = dict(
        onboarding_id="ONB-TEST-001",
        community_id="DESERT_RIDGE_TEST",
        display_name="Desert Ridge Test",
        state="AZ",
        county="Maricopa",
        property_id_prefix="DRT-",
        listing_service="TEST_MLS",
        parcel_authority="TEST_ASSESSOR",
        recorder_authority="TEST_RECORDER",
        parent_platform_version="0.1.114",
        parent_platform_fingerprint="a" * 64,
        community_specific=("phase taxonomy", "builder roster"),
        source_specific=("listing field map", "parcel identifier map"),
    )
    data.update(overrides)
    return CommunityOnboardingInput(**data)


def test_contract_loads_locked_m10_003():
    c = contract()
    assert c["ticket"] == "M10-003"
    assert c["status"] == "LOCKED"


def test_valid_onboarding_is_deterministic():
    a = generate_bootstrap(data=valid_input(), contract=contract())
    b = generate_bootstrap(data=valid_input(), contract=contract())
    assert a.community_config == b.community_config
    assert a.onboarding_manifest == b.onboarding_manifest
    assert a.bootstrap_fingerprint == b.bootstrap_fingerprint


def test_generated_bootstrap_preserves_exact_parent_lineage():
    result = generate_bootstrap(data=valid_input(), contract=contract())
    assert result.community_config["lineage"]["parent_platform_version"] == "0.1.114"
    assert result.community_config["lineage"]["parent_platform_fingerprint"] == "a" * 64
    assert result.onboarding_manifest["parent_platform_fingerprint"] == "a" * 64


def test_generated_output_has_no_timestamp_or_hidden_defaults():
    result = generate_bootstrap(data=valid_input(), contract=contract())
    assert "generated_at" not in result.onboarding_manifest
    assert_no_protected_defaults(result, ("SAN_TAN_HEIGHTS", "San Tan Heights", "Pinal", "ARMLS"))


def test_protected_san_tan_heights_identity_is_rejected():
    with pytest.raises(ValueError, match="protected community"):
        generate_bootstrap(data=valid_input(community_id="SAN_TAN_HEIGHTS"), contract=contract())


@pytest.mark.parametrize(
    "field,value,match",
    [
        ("community_id", "bad id", "upper snake case"),
        ("display_name", " ", "display_name required"),
        ("state", "Arizona", "two-letter"),
        ("county", "", "county required"),
        ("property_id_prefix", "", "property_id_prefix required"),
        ("listing_service", "", "listing_service required"),
        ("parcel_authority", "", "parcel_authority required"),
        ("recorder_authority", "", "recorder_authority required"),
        ("parent_platform_fingerprint", "abc", "sha256"),
    ],
)
def test_invalid_required_inputs_fail_closed(field, value, match):
    with pytest.raises(ValueError, match=match):
        generate_bootstrap(data=valid_input(**{field: value}), contract=contract())


def test_assumptions_must_be_explicit_and_nonempty():
    with pytest.raises(ValueError, match="community_specific assumptions"):
        generate_bootstrap(data=valid_input(community_specific=()), contract=contract())
    with pytest.raises(ValueError, match="source_specific assumptions"):
        generate_bootstrap(data=valid_input(source_specific=()), contract=contract())


def test_assumption_order_and_duplicates_do_not_change_fingerprint():
    a = generate_bootstrap(
        data=valid_input(
            community_specific=("builder roster", "phase taxonomy", "builder roster"),
            source_specific=("parcel identifier map", "listing field map"),
        ),
        contract=contract(),
    )
    b = generate_bootstrap(data=valid_input(), contract=contract())
    assert a.bootstrap_fingerprint == b.bootstrap_fingerprint


def test_leakage_guard_rejects_protected_tokens():
    result = generate_bootstrap(data=valid_input(display_name="San Tan Heights Copy"), contract=contract())
    with pytest.raises(ValueError, match="leakage"):
        assert_no_protected_defaults(result, ("San Tan Heights",))
