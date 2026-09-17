from __future__ import annotations
from pathlib import Path
import yaml
SEVERITY={'INFO':0,'WARNING':1,'ERROR':2,'CRITICAL':3}
class ContainmentRuleRegistry:
    def __init__(self,rules): self.rules=tuple(rules)
    @classmethod
    def from_repository(cls,root:Path):
        data=yaml.safe_load((root/'registries/operations/containment-rules.yaml').read_text())
        return cls(data['rules'])
    def resolve(self,incident_type,severity):
        candidates=[]
        for r in self.rules:
            if incident_type in r['incident_types'] and SEVERITY[severity]>=SEVERITY[r['minimum_severity']]: candidates.append(r)
        return None if not candidates else candidates[0]
