from pathlib import Path
import yaml
class BreakGlassPolicyError(ValueError): pass
class BreakGlassPolicyRegistry:
    def __init__(self, raw): self.raw=raw
    @classmethod
    def from_repository(cls, root: Path):
        raw=yaml.safe_load((Path(root)/'registries/security/break-glass-policy-v1.0.yaml').read_text())
        if raw.get('status')!='LOCKED': raise BreakGlassPolicyError('break-glass policy must be LOCKED')
        if int(raw.get('max_duration_minutes',0))<=0: raise BreakGlassPolicyError('positive max duration required')
        if not raw.get('issuer_roles') or not raw.get('required_action'): raise BreakGlassPolicyError('issuer controls required')
        return cls(raw)
    @property
    def max_duration_minutes(self): return int(self.raw['max_duration_minutes'])
    @property
    def issuer_roles(self): return frozenset(self.raw['issuer_roles'])
    @property
    def prohibited_actions(self): return frozenset(self.raw.get('prohibited_actions') or [])
