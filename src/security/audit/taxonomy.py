from pathlib import Path
import yaml
class SecurityEventRegistryError(ValueError): pass
class SecurityEventRegistry:
    def __init__(self, events): self.events=events
    @classmethod
    def from_repository(cls,root:Path):
        raw=yaml.safe_load((Path(root)/'registries/security/security-events-v1.0.yaml').read_text())
        if raw.get('status')!='LOCKED': raise SecurityEventRegistryError('security event registry must be LOCKED')
        events=raw.get('events') or {}
        if not events: raise SecurityEventRegistryError('security event taxonomy required')
        return cls(events)
    def require(self,event_type):
        if event_type not in self.events: raise SecurityEventRegistryError(f'unknown security event: {event_type}')
        return self.events[event_type]
