from __future__ import annotations
from dataclasses import dataclass
from .registry import PriorityRegistry

@dataclass(frozen=True)
class ResolvedPriority:
    priority_class: str
    priority_score: int
    rule_id: str
    registry_version: str

class PriorityResolver:
    def __init__(self, registry: PriorityRegistry): self.registry=registry

    def resolve(self, *, trigger_type: str, change_class: str | None = None, reason_code: str | None = None) -> ResolvedPriority:
        context={'trigger_type':trigger_type,'change_class':change_class,'reason_code':reason_code}
        for rule in self.registry.rules:
            if all(context.get(k)==v for k,v in rule.when.items()):
                return ResolvedPriority(rule.priority_class,self.registry.classes[rule.priority_class],rule.rule_id,self.registry.version)
        pc=self.registry.default
        return ResolvedPriority(pc,self.registry.classes[pc],'PRIORITY_DEFAULT',self.registry.version)
