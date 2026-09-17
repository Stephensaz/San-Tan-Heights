from dataclasses import dataclass
from datetime import datetime

@dataclass(frozen=True)
class SignedServiceAssertion:
    service_id: str
    credential_id: str
    auth_method: str
    audience: str
    issued_at: datetime
    expires_at: datetime
    nonce: str
    signature: str

@dataclass(frozen=True)
class AuthenticatedServicePrincipal:
    service_id: str
    database_role: str
    trust_tier: str
    capabilities: frozenset[str]
    credential_id: str
    authenticated_at: datetime
