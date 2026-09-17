from pathlib import Path
import yaml
from .models import ServiceIdentity

class ServiceIdentityRegistryError(ValueError):
    pass

class ServiceIdentityRegistry:
    def __init__(self, registry_id: str, version: str, services: tuple[ServiceIdentity, ...]):
        self.registry_id=registry_id; self.version=version
        self._services={s.service_id:s for s in services}
        if len(self._services)!=len(services): raise ServiceIdentityRegistryError('duplicate service_id')
        roles=[s.database_role for s in services]
        if len(roles)!=len(set(roles)): raise ServiceIdentityRegistryError('database_role must be unique per service')
    @classmethod
    def from_repository(cls, root: Path):
        raw=yaml.safe_load((root/'registries/security/service-identities-v1.0.yaml').read_text())
        if raw.get('status')!='LOCKED': raise ServiceIdentityRegistryError('service identity registry must be LOCKED')
        services=[]
        for row in raw.get('services',[]):
            required={'service_id','status','trust_tier','database_role','allowed_auth_methods','capabilities'}
            if not required.issubset(row): raise ServiceIdentityRegistryError(f'incomplete service identity: {row}')
            if row['status'] not in {'ACTIVE','DISABLED'}: raise ServiceIdentityRegistryError('invalid service status')
            if not row['allowed_auth_methods']: raise ServiceIdentityRegistryError('service needs an authentication method')
            services.append(ServiceIdentity(row['service_id'],row['status'],row['trust_tier'],row['database_role'],frozenset(row['allowed_auth_methods']),frozenset(row['capabilities'])))
        if not services: raise ServiceIdentityRegistryError('empty service identity registry')
        return cls(raw['registry_id'],raw['version'],tuple(services))
    def get(self, service_id: str) -> ServiceIdentity:
        try: return self._services[service_id]
        except KeyError as exc: raise ServiceIdentityRegistryError(f'unknown service_id: {service_id}') from exc
    def require_active(self, service_id: str) -> ServiceIdentity:
        identity=self.get(service_id)
        if identity.status!='ACTIVE': raise ServiceIdentityRegistryError(f'service disabled: {service_id}')
        return identity
    def all(self): return tuple(sorted(self._services.values(), key=lambda x:x.service_id))
