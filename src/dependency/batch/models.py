from __future__ import annotations
from dataclasses import dataclass, field
from uuid import UUID

BATCH_STATES={'DISCOVERING','EVALUATING','COMPLETE','PARTIAL_FAILURE','BLOCKED'}
ITEM_STATES={'PENDING','EVALUATING','COMPLETE','FAILED','BLOCKED'}

@dataclass(frozen=True)
class DependencyChangeBatch:
    batch_id: UUID
    dependency_type: str
    source_change_id: str
    correlation_id: UUID
    old_version: str|None=None
    new_version: str|None=None
    batch_state: str='DISCOVERING'

@dataclass(frozen=True)
class DependencyChangeItem:
    item_id: UUID
    batch_id: UUID
    property_id: UUID
    dependency_id: str
    change_class: str
    old_fingerprint: str|None=None
    new_fingerprint: str|None=None
    required_state_blocked: bool=False

@dataclass(frozen=True)
class BatchEvaluationSummary:
    batch_id: UUID
    evaluated_items: int
    decision_counts: dict[str,int]=field(default_factory=dict)
    failed_items: int=0

    @property
    def affected_items(self)->int:
        return sum(self.decision_counts.get(x,0) for x in ('DIRTY','BLOCKED','INVALIDATION_REQUIRED','REVIEW_REQUIRED'))
