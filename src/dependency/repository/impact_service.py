from __future__ import annotations
from uuid import UUID
from src.kernel.events import EventDraft, EventWriter
from src.dependency.evaluator import ImpactDecision
from .impact_repository import ImpactRepository

_EVENT_BY_DECISION={
 'DIRTY':'REPORT_MARKED_DIRTY',
 'BLOCKED':'REPORT_BLOCKED_BY_DEPENDENCY',
 'INVALIDATION_REQUIRED':'REPORT_INVALIDATION_RECOMMENDED',
 'REVIEW_REQUIRED':'REPORT_REVIEW_REQUIRED',
}

class ImpactPersistenceService:
    def __init__(self, root, repository=None, event_writer=None, rule_version='1.0.0'):
        self.repository=repository or ImpactRepository(); self.events=event_writer or EventWriter(root); self.rule_version=rule_version
    def persist(self,cursor,*,source_event_id:UUID,correlation_id:UUID,decision:ImpactDecision,batch_id:UUID|None=None):
        iid=self.repository.persist(cursor,source_event_id=source_event_id,correlation_id=correlation_id,decision=decision,rule_version=self.rule_version,batch_id=batch_id)
        payload={'impact_evaluation_id':str(iid),'report_variant':decision.report_variant,'dependency_type':decision.dependency_type,'dependency_id':decision.dependency_id,'decision':decision.decision,'rule_id':decision.rule_id}
        self.events.write(cursor,EventDraft(event_type='REPORT_IMPACT_EVALUATED',source_system='DEPENDENCY_SERVICE',actor_type='SYSTEM',actor_id='DEPENDENCY_SERVICE',correlation_id=correlation_id,causation_event_id=source_event_id,property_id=decision.property_id,report_id=decision.report_id,reason_code=decision.reason_code,payload=payload))
        material=_EVENT_BY_DECISION.get(decision.decision)
        if material:
            self.events.write(cursor,EventDraft(event_type=material,source_system='DEPENDENCY_SERVICE',actor_type='SYSTEM',actor_id='DEPENDENCY_SERVICE',correlation_id=correlation_id,causation_event_id=source_event_id,property_id=decision.property_id,report_id=decision.report_id,reason_code=decision.reason_code,payload=payload))
        return iid
