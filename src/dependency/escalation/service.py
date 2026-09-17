from __future__ import annotations
from uuid import uuid4
from src.dependency.evaluator import ImpactDecision

class ReviewItemRepository:
    INSERT='''INSERT INTO operations.review_items
(review_item_id,review_type,status,property_id,report_id,source_event_id,reason_code,safe_context,correlation_id)
VALUES (%s,'DEPENDENCY_IMPACT_REVIEW','OPEN',%s,%s,%s,%s,%s,%s) RETURNING review_item_id'''
    def create(self,cursor,*,decision,source_event_id,correlation_id):
        rid=uuid4(); context={'dependency_type':decision.dependency_type,'dependency_id':decision.dependency_id,'report_variant':decision.report_variant,'change_class':decision.change_class}
        cursor.execute(self.INSERT,(rid,decision.property_id,decision.report_id,source_event_id,decision.reason_code,context,correlation_id)); row=cursor.fetchone()
        return row[0] if row else rid

class DependencyImpactEscalationService:
    def __init__(self,review_repository=None): self.reviews=review_repository or ReviewItemRepository()
    def escalate(self,cursor,*,decision:ImpactDecision,source_event_id,correlation_id):
        if decision.decision=='REVIEW_REQUIRED':
            return {'action':'REVIEW_ITEM_CREATED','review_item_id':self.reviews.create(cursor,decision=decision,source_event_id=source_event_id,correlation_id=correlation_id)}
        if decision.decision=='INVALIDATION_REQUIRED':
            return {'action':'INVALIDATION_RECOMMENDED'}
        if decision.decision=='BLOCKED':
            return {'action':'BLOCKED_DOWNSTREAM'}
        return {'action':'NONE'}
