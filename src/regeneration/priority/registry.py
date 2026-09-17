from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Any
import yaml

VALID_CLASSES = {'CRITICAL','HIGH','NORMAL','BULK','LOW'}

class PriorityRegistryError(ValueError): pass

@dataclass(frozen=True)
class PriorityRule:
    rule_id: str
    priority_class: str
    when: dict[str, Any]

@dataclass(frozen=True)
class PriorityRegistry:
    registry_id: str
    version: str
    classes: dict[str,int]
    rules: tuple[PriorityRule,...]
    default: str

    @classmethod
    def from_repository(cls, root: Path):
        path=root/'registries/regeneration/priorities.yaml'
        raw=yaml.safe_load(path.read_text())
        if raw.get('registry_id')!='STH-REGENERATION-PRIORITY-v1.0': raise PriorityRegistryError('unexpected priority registry id')
        classes={str(k):int(v) for k,v in raw.get('classes',{}).items()}
        if set(classes)!=VALID_CLASSES: raise PriorityRegistryError('priority classes must be exactly CRITICAL/HIGH/NORMAL/BULK/LOW')
        if len(set(classes.values()))!=len(classes): raise PriorityRegistryError('priority scores must be unique')
        rules=[]; seen=set()
        for item in raw.get('rules',[]):
            rid=str(item['rule_id'])
            if rid in seen: raise PriorityRegistryError(f'duplicate rule_id: {rid}')
            seen.add(rid)
            pc=str(item['priority_class'])
            if pc not in classes: raise PriorityRegistryError(f'unknown priority class: {pc}')
            when=dict(item.get('when') or {})
            if not when: raise PriorityRegistryError(f'priority rule {rid} has empty predicate')
            rules.append(PriorityRule(rid,pc,when))
        default=str(raw.get('default'))
        if default not in classes: raise PriorityRegistryError('default priority class is unknown')
        return cls(raw['registry_id'],str(raw['version']),classes,tuple(rules),default)
