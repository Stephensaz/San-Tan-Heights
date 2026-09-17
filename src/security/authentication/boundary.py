from datetime import datetime, timezone, timedelta
import base64, hashlib, hmac
from typing import Callable
from src.shared.canonical_json import canonical_json
from src.security.identity import ServiceIdentityRegistry
from .models import SignedServiceAssertion, AuthenticatedServicePrincipal

class ServiceAuthenticationError(PermissionError):
    pass

def _utc(dt: datetime) -> datetime:
    if dt.tzinfo is None: raise ServiceAuthenticationError('timestamps must be timezone-aware')
    return dt.astimezone(timezone.utc)

def assertion_payload(assertion: SignedServiceAssertion) -> dict:
    return {
        'service_id':assertion.service_id,'credential_id':assertion.credential_id,
        'auth_method':assertion.auth_method,'audience':assertion.audience,
        'issued_at':_utc(assertion.issued_at).isoformat().replace('+00:00','Z'),
        'expires_at':_utc(assertion.expires_at).isoformat().replace('+00:00','Z'),
        'nonce':assertion.nonce,
    }

def sign_hmac_sha256(assertion: SignedServiceAssertion, key: bytes) -> str:
    digest=hmac.new(key,canonical_json(assertion_payload(assertion)).encode('utf-8'),hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b'=').decode('ascii')

class ServiceAuthenticationBoundary:
    def __init__(self, registry: ServiceIdentityRegistry, key_resolver: Callable[[str,str], bytes|None], *, expected_audience='sth-internal', max_ttl_seconds=300, clock_skew_seconds=30):
        self.registry=registry; self.key_resolver=key_resolver; self.expected_audience=expected_audience
        self.max_ttl=timedelta(seconds=max_ttl_seconds); self.clock_skew=timedelta(seconds=clock_skew_seconds)
    def authenticate(self, assertion: SignedServiceAssertion, *, now: datetime|None=None) -> AuthenticatedServicePrincipal:
        identity=self.registry.require_active(assertion.service_id)
        if assertion.auth_method not in identity.allowed_auth_methods: raise ServiceAuthenticationError('authentication method not allowed')
        if assertion.auth_method!='HMAC_SHA256_ASSERTION': raise ServiceAuthenticationError('unsupported authentication method')
        if assertion.audience!=self.expected_audience: raise ServiceAuthenticationError('invalid audience')
        issued=_utc(assertion.issued_at); expires=_utc(assertion.expires_at); current=_utc(now or datetime.now(timezone.utc))
        if expires<=issued or expires-issued>self.max_ttl: raise ServiceAuthenticationError('invalid assertion lifetime')
        if issued-current>self.clock_skew: raise ServiceAuthenticationError('assertion issued in future')
        if current-expires>self.clock_skew: raise ServiceAuthenticationError('assertion expired')
        if not assertion.nonce or len(assertion.nonce)<16: raise ServiceAuthenticationError('nonce too short')
        key=self.key_resolver(assertion.service_id,assertion.credential_id)
        if not key: raise ServiceAuthenticationError('unknown credential')
        expected=sign_hmac_sha256(assertion,key)
        if not hmac.compare_digest(expected,assertion.signature): raise ServiceAuthenticationError('invalid signature')
        return AuthenticatedServicePrincipal(identity.service_id,identity.database_role,identity.trust_tier,identity.capabilities,assertion.credential_id,current)
    def require_capability(self, principal: AuthenticatedServicePrincipal, capability: str) -> None:
        if capability not in principal.capabilities: raise ServiceAuthenticationError(f'capability denied: {capability}')
