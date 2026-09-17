from __future__ import annotations
from pathlib import Path
import yaml
class RecoveryActionRegistry:
    def __init__(self,actions): self.actions={a['command_type']:a for a in actions}
    @classmethod
    def from_repository(cls,root:Path):
        return cls(yaml.safe_load((root/'registries/operations/recovery-actions.yaml').read_text())['actions'])
    def validate(self,command_type,payload,incident_state):
        rule=self.actions.get(command_type)
        if not rule: raise ValueError('unknown recovery command type')
        if incident_state not in rule['allowed_incident_states']: raise ValueError('recovery command not allowed for incident state')
        missing=[k for k in rule.get('required_payload',[]) if payload.get(k) in (None,'')]
        if missing: raise ValueError('missing recovery payload: '+','.join(sorted(missing)))
        return rule
