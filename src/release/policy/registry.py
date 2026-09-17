from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import yaml

_VARIANTS=frozenset({'AGENT','SELLER','PUBLIC'})
_CHANNELS=frozenset({'WEB','PDF_DOWNLOAD','PRINT'})
_DUPLICATE=frozenset({'REJECT_CONFLICT'})
_SORT=('property_id','report_variant','channel')

class ReleasePolicyRegistryError(ValueError): pass

@dataclass(frozen=True)
class ReleasePolicy:
    policy_id: str
    registry_id: str
    version: str
    description: str
    allowed_variants: frozenset[str]
    allowed_channels: frozenset[str]
    channel_optional: bool
    duplicate_behavior: str
    membership_sort: tuple[str,...]
    require_membership_freeze: bool

class ReleasePolicyRegistry:
    def __init__(self, policies: dict[str,ReleasePolicy], registry_id: str, version: str):
        self._policies=policies; self.registry_id=registry_id; self.version=version
    @classmethod
    def from_repository(cls, root: Path) -> 'ReleasePolicyRegistry':
        raw=yaml.safe_load((Path(root)/'registries/releases/release-policy-v1.0.yaml').read_text())
        rid=str(raw.get('registry_id') or ''); version=str(raw.get('version') or '')
        if not rid or not version: raise ReleasePolicyRegistryError('registry id/version required')
        policies={}
        for key,p in (raw.get('policies') or {}).items():
            pid=str(p.get('policy_id') or '')
            if key!=pid or not pid: raise ReleasePolicyRegistryError('policy key/id mismatch')
            variants=frozenset(p.get('allowed_variants') or [])
            channels=frozenset(p.get('allowed_channels') or [])
            if not variants or variants-_VARIANTS: raise ReleasePolicyRegistryError(f'unknown/empty variants for {pid}')
            if channels-_CHANNELS: raise ReleasePolicyRegistryError(f'unknown channels for {pid}')
            duplicate=str(p.get('duplicate_behavior') or '')
            if duplicate not in _DUPLICATE: raise ReleasePolicyRegistryError(f'unsupported duplicate behavior: {duplicate}')
            sort=tuple(p.get('membership_sort') or [])
            if sort!=_SORT: raise ReleasePolicyRegistryError('membership_sort must be deterministic canonical order')
            policies[pid]=ReleasePolicy(pid,rid,version,str(p.get('description') or ''),variants,channels,bool(p.get('channel_optional')),duplicate,sort,bool(p.get('require_membership_freeze')))
        if not policies: raise ReleasePolicyRegistryError('at least one release policy required')
        return cls(policies,rid,version)
    def get(self, policy_id: str) -> ReleasePolicy:
        try: return self._policies[policy_id]
        except KeyError as exc: raise ReleasePolicyRegistryError(f'unknown release policy: {policy_id}') from exc
    @property
    def policy_ids(self): return tuple(sorted(self._policies))
