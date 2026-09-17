from dataclasses import dataclass

@dataclass(frozen=True)
class ServiceIdentity:
    service_id: str
    status: str
    trust_tier: str
    database_role: str
    allowed_auth_methods: frozenset[str]
    capabilities: frozenset[str]
