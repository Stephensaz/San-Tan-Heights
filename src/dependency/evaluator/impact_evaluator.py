from __future__ import annotations
from dataclasses import dataclass
from typing import Literal
from src.dependency.rules.registry import DependencyImpactRuleRegistry
from src.dependency.lookup import DependencyConsumer

ChangeClass = Literal['NORMAL_UPDATE','SOURCE_REFRESH','GOVERNANCE_CHANGE','CORRECTION','MATERIAL_CORRECTION','IDENTITY_CORRECTION','INVALIDATING_CORRECTION']
Decision = Literal['NO_IMPACT','DIRTY','BLOCKED','INVALIDATION_REQUIRED','REVIEW_REQUIRED']

@dataclass(frozen=True)
class DependencyChange:
    dependency_type: str
    dependency_id: str
    old_semantic_fingerprint: str | None
    new_semantic_fingerprint: str | None
    change_class: ChangeClass
    required_state_blocked: bool=False

@dataclass(frozen=True)
class ImpactDecision:
    property_id: object
    report_id: object | None
    report_variant: str
    dependency_type: str
    dependency_id: str
    stored_fingerprint: str
    current_fingerprint: str | None
    change_class: str
    decision: Decision
    rule_id: str
    reason_code: str

class ImpactEvaluator:
    def __init__(self, registry: DependencyImpactRuleRegistry|None=None):
        self.registry=registry or DependencyImpactRuleRegistry()

    def evaluate(self, change: DependencyChange, consumer: DependencyConsumer) -> ImpactDecision:
        rule=self.registry.get(change.dependency_type)
        decision: Decision
        reason: str
        if rule.requires_consumption and consumer.stored_semantic_fingerprint is None:
            decision,reason='NO_IMPACT','DEPENDENCY_NOT_CONSUMED'
        elif consumer.stored_semantic_fingerprint == change.new_semantic_fingerprint:
            decision,reason='NO_IMPACT','DEPENDENCY_SEMANTICS_UNCHANGED'
        elif not rule.variants.get(consumer.report_variant,False):
            decision,reason='NO_IMPACT','VARIANT_NOT_AFFECTED'
        elif change.change_class == 'INVALIDATING_CORRECTION':
            decision,reason=rule.invalidating_change,'INVALIDATING_CORRECTION'
        elif change.required_state_blocked:
            decision,reason=rule.blocked_change,'REQUIRED_DEPENDENCY_BLOCKED'
        elif change.change_class not in {'NORMAL_UPDATE','SOURCE_REFRESH','GOVERNANCE_CHANGE','CORRECTION','MATERIAL_CORRECTION','IDENTITY_CORRECTION'}:
            decision,reason='REVIEW_REQUIRED','CHANGE_CLASS_REVIEW_REQUIRED'
        else:
            decision,reason=rule.normal_change,'DEPENDENCY_SEMANTIC_CHANGE'
        return ImpactDecision(consumer.property_id,consumer.report_id,consumer.report_variant,change.dependency_type,change.dependency_id,consumer.stored_semantic_fingerprint,change.new_semantic_fingerprint,change.change_class,decision,rule.rule_id,reason)
