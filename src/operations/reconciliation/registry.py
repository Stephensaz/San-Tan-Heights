from __future__ import annotations
import yaml
from pathlib import Path
class ReconciliationRuleRegistry:
    def __init__(self,path):
        data=yaml.safe_load(Path(path).read_text()); self.registry_id=data['registry_id']; self._rules={r['rule_id']:r for r in data['rules']}
        if len(self._rules)!=len(data['rules']): raise ValueError('duplicate reconciliation rule')
    def get(self,rule_id):
        try:return self._rules[rule_id]
        except KeyError as e: raise ValueError(f'unknown reconciliation rule: {rule_id}') from e
    @property
    def rule_ids(self): return tuple(sorted(self._rules))
