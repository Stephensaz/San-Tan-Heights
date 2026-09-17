from pathlib import Path

import pytest

from src.presentation.package import PresentationAudience
from src.presentation.routing import PropertyRoutingRegistry, StablePropertyRouter

ROOT = Path(__file__).resolve().parents[3]
ROUTING_REGISTRY = ROOT / "registries" / "presentation" / "property-routing-v1.0.yaml"
PROPERTY_ID = "aaaaaaaa-1111-1111-1111-111111111111"


def router():
    return StablePropertyRouter(PropertyRoutingRegistry.load(ROUTING_REGISTRY))


def test_property_routing_registry_is_locked_identity_only():
    registry = PropertyRoutingRegistry.load(ROUTING_REGISTRY)
    assert registry.status == "LOCKED"
    assert registry.base_path == "/properties"
    assert registry.rules["route_is_version_independent"] is True
    assert registry.rules["route_is_identity_only"] is True
    assert registry.rules["route_does_not_authorize_access"] is True
    assert registry.rules["allow_address_in_route"] is False
    assert registry.rules["allow_report_version_in_route"] is False
    assert registry.rules["allow_presentation_hash_in_route"] is False


def test_stable_routes_are_deterministic_for_each_audience():
    assert router().build(PROPERTY_ID, PresentationAudience.AGENT).path == f"/properties/{PROPERTY_ID}/agent"
    assert router().build(PROPERTY_ID, PresentationAudience.SELLER).path == f"/properties/{PROPERTY_ID}/seller"
    assert router().build(PROPERTY_ID, PresentationAudience.PUBLIC).path == f"/properties/{PROPERTY_ID}/public"
    first = router().build(PROPERTY_ID, PresentationAudience.PUBLIC)
    second = router().build(PROPERTY_ID, PresentationAudience.PUBLIC)
    assert first.fingerprint == second.fingerprint


def test_route_round_trip_preserves_property_identity_and_audience():
    built = router().build(PROPERTY_ID, PresentationAudience.SELLER)
    resolved = router().resolve(built.path)
    assert resolved == built


def test_router_rejects_noncanonical_or_non_uuid_identity():
    with pytest.raises(ValueError, match="canonical lowercase UUID"):
        router().build(PROPERTY_ID.upper(), PresentationAudience.PUBLIC)
    with pytest.raises(ValueError, match="canonical UUID"):
        router().build("123-example-st", PresentationAudience.PUBLIC)


def test_router_rejects_unknown_or_noncanonical_paths():
    with pytest.raises(ValueError, match="unknown presentation audience"):
        router().resolve(f"/properties/{PROPERTY_ID}/private")
    with pytest.raises(ValueError, match="query or fragment"):
        router().resolve(f"/properties/{PROPERTY_ID}/public?version=2")
    with pytest.raises(ValueError, match="stable property routing contract"):
        router().resolve(f"/homes/{PROPERTY_ID}/public")
