from __future__ import annotations
from collections import Counter
from uuid import UUID, uuid5, NAMESPACE_URL
from src.dependency.evaluator import DependencyChange, ImpactEvaluator
from src.dependency.lookup import DependencyReverseLookup
from src.dependency.repository import ImpactPersistenceService
from .models import BatchEvaluationSummary

class BulkImpactEvaluator:
    def __init__(self, repository, reverse_lookup=None, evaluator=None, persistence=None):
        self.repository=repository
        self.lookup=reverse_lookup or DependencyReverseLookup()
        self.evaluator=evaluator or ImpactEvaluator()
        self.persistence=persistence

    @staticmethod
    def source_event_id(batch_id,item_id):
        return uuid5(NAMESPACE_URL,f'sth:dependency-batch:{batch_id}:item:{item_id}')

    def evaluate_claimed(self,cursor,*,batch_id:UUID,dependency_type:str,correlation_id:UUID,limit:int=250):
        items=self.repository.claim_items(cursor,batch_id,limit)
        counts=Counter(); failures=0
        for item in items:
            try:
                change=DependencyChange(dependency_type,item.dependency_id,item.old_fingerprint,item.new_fingerprint,item.change_class,item.required_state_blocked)
                consumers=[c for c in self.lookup.lookup(cursor,dependency_type,item.dependency_id) if c.property_id==item.property_id]
                item_counts=Counter()
                for consumer in consumers:
                    decision=self.evaluator.evaluate(change,consumer)
                    item_counts[decision.decision]+=1; counts[decision.decision]+=1
                    if self.persistence:
                        self.persistence.persist(cursor,source_event_id=self.source_event_id(batch_id,item.item_id),correlation_id=correlation_id,decision=decision,batch_id=batch_id)
                if not consumers: item_counts['NO_IMPACT']+=1; counts['NO_IMPACT']+=1
                self.repository.complete_item(cursor,item.item_id,dict(sorted(item_counts.items())))
            except Exception:
                failures+=1; self.repository.fail_item(cursor,item.item_id,'BULK_IMPACT_EVALUATION_FAILED')
        return BatchEvaluationSummary(batch_id,len(items),dict(sorted(counts.items())),failures)
