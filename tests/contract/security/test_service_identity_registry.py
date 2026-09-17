from pathlib import Path
from src.security.identity import ServiceIdentityRegistry
ROOT=Path(__file__).resolve().parents[3]

def test_service_identity_registry_is_locked_complete_and_one_role_per_service():
    reg=ServiceIdentityRegistry.from_repository(ROOT)
    assert reg.registry_id=='STH-SERVICE-IDENTITIES-v1.0'
    services=reg.all()
    assert {'SNAPSHOT_SERVICE','REPORT_BUILDER','RENDERER','PUBLICATION_SERVICE','REGENERATION_WORKER','RELEASE_SERVICE','OPERATIONS_SERVICE','PUBLIC_DELIVERY'} <= {s.service_id for s in services}
    assert len({s.database_role for s in services})==len(services)
    assert all(s.allowed_auth_methods==frozenset({'HMAC_SHA256_ASSERTION'}) for s in services)

def test_public_delivery_is_read_only_by_capability():
    s=ServiceIdentityRegistry.from_repository(ROOT).get('PUBLIC_DELIVERY')
    assert s.trust_tier=='EDGE_READ_ONLY'
    assert all(cap.endswith('.read') for cap in s.capabilities)
    assert 'database.migrate' not in s.capabilities
