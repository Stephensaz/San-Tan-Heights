from pathlib import Path
import yaml
from .models import HumanRole

class HumanRoleRegistryError(ValueError): pass

EXPECTED_ROLES=frozenset({'PUBLIC','SELLER','AGENT','OPERATIONS','ADMIN'})
CLASSIFICATIONS=frozenset({'PUBLIC_DATA','SELLER_DATA','AGENT_INTERNAL','OPERATIONS_INTERNAL','SYSTEM_INTERNAL','RESTRICTED'})
SCOPE_MODES=frozenset({'NONE','ASSIGNED','FLEET'})

class HumanRoleRegistry:
    def __init__(self, registry_id, version, roles, actions):
        self.registry_id=registry_id; self.version=version; self._roles=roles; self._actions=actions
    @classmethod
    def from_repository(cls, root: Path):
        raw=yaml.safe_load((Path(root)/'registries/security/human-roles-v1.0.yaml').read_text())
        if raw.get('status')!='LOCKED': raise HumanRoleRegistryError('human role registry must be LOCKED')
        rows=raw.get('roles') or {}
        if frozenset(rows)!=EXPECTED_ROLES: raise HumanRoleRegistryError('human roles must exactly match security contract')
        actions=raw.get('actions') or {}
        if not actions: raise HumanRoleRegistryError('action registry required')
        roles={}
        for role_id,row in rows.items():
            if row.get('status') not in {'ACTIVE','DISABLED'}: raise HumanRoleRegistryError(f'invalid role status: {role_id}')
            scope=str(row.get('property_scope_mode') or '')
            if scope not in SCOPE_MODES: raise HumanRoleRegistryError(f'invalid property scope mode: {role_id}')
            classes=frozenset(row.get('classifications') or [])
            if not classes or classes-CLASSIFICATIONS: raise HumanRoleRegistryError(f'invalid classifications: {role_id}')
            permitted=frozenset(row.get('actions') or [])
            if not permitted: raise HumanRoleRegistryError(f'role needs actions: {role_id}')
            if '*' not in permitted and permitted-frozenset(actions): raise HumanRoleRegistryError(f'unknown action on role: {role_id}')
            roles[role_id]=HumanRole(role_id,row['status'],scope,classes,permitted)
        if roles['AGENT'].actions==roles['ADMIN'].actions or 'RESTRICTED' in roles['AGENT'].classifications:
            raise HumanRoleRegistryError('agent must not be admin-equivalent')
        return cls(raw['registry_id'],raw['version'],roles,actions)
    def get(self, role_id):
        try: return self._roles[role_id]
        except KeyError as exc: raise HumanRoleRegistryError(f'unknown role: {role_id}') from exc
    def action(self, action):
        try: return self._actions[action]
        except KeyError as exc: raise HumanRoleRegistryError(f'unknown action: {action}') from exc
    @property
    def role_ids(self): return tuple(sorted(self._roles))
