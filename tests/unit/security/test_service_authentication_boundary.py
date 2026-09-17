from dataclasses import replace
from datetime import datetime, timezone, timedelta
from pathlib import Path
import pytest
from src.security.identity import ServiceIdentityRegistry
from src.security.authentication import SignedServiceAssertion, ServiceAuthenticationBoundary, ServiceAuthenticationError, sign_hmac_sha256
ROOT=Path(__file__).resolve().parents[3]
KEY=b'test-key-material-not-production'
NOW=datetime(2026,9,16,21,0,tzinfo=timezone.utc)

def assertion(service='PUBLICATION_SERVICE', audience='sth-internal', issued=NOW, expires=None, nonce='1234567890abcdef', credential='cred-1'):
    a=SignedServiceAssertion(service,credential,'HMAC_SHA256_ASSERTION',audience,issued,expires or issued+timedelta(minutes=2),nonce,'')
    return replace(a, signature=sign_hmac_sha256(a,KEY))

def boundary(key=KEY):
    reg=ServiceIdentityRegistry.from_repository(ROOT)
    return ServiceAuthenticationBoundary(reg, lambda service_id, credential_id: key if credential_id=='cred-1' else None)

def test_valid_signed_assertion_authenticates_to_registry_identity():
    p=boundary().authenticate(assertion(),now=NOW)
    assert p.service_id=='PUBLICATION_SERVICE'
    assert p.database_role=='sth_publication_service'
    assert 'publication.write' in p.capabilities

def test_claimed_identity_without_valid_signature_fails_closed():
    a=replace(assertion(),signature='not-a-signature')
    with pytest.raises(ServiceAuthenticationError): boundary().authenticate(a,now=NOW)

def test_wrong_audience_expired_unknown_credential_and_long_lifetime_fail():
    cases=[
      assertion(audience='other'),
      assertion(issued=NOW-timedelta(minutes=10),expires=NOW-timedelta(minutes=8)),
      assertion(credential='unknown'),
      assertion(expires=NOW+timedelta(minutes=10)),
    ]
    for a in cases:
        with pytest.raises(ServiceAuthenticationError): boundary().authenticate(a,now=NOW)

def test_capability_is_checked_after_authentication():
    p=boundary().authenticate(assertion('PUBLIC_DELIVERY'),now=NOW)
    boundary().require_capability(p,'publication.current_public.read')
    with pytest.raises(ServiceAuthenticationError): boundary().require_capability(p,'publication.write')
