from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID, uuid4
from src.dependency.evaluator import ImpactDecision

@dataclass(frozen=True)
class PersistedImpact:
    impact_evaluation_id: UUID
    source_event_id: UUID
    correlation_id: UUID
    decision: ImpactDecision

class ImpactRepository:
    INSERT='''INSERT INTO orchestration.report_impact_evaluations
(impact_evaluation_id,source_event_id,batch_id,property_id,report_id,report_variant,dependency_type,dependency_id,stored_fingerprint,current_fingerprint,change_class,decision,impact_rule_id,impact_rule_version,reason_code,correlation_id)
VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
ON CONFLICT(source_event_id,property_id,report_variant,dependency_type,dependency_id) DO NOTHING
RETURNING impact_evaluation_id'''
    FIND='''SELECT impact_evaluation_id,decision,reason_code FROM orchestration.report_impact_evaluations WHERE source_event_id=%s AND property_id=%s AND report_variant=%s AND dependency_type=%s AND dependency_id=%s'''
    def persist(self,cursor,*,source_event_id:UUID,correlation_id:UUID,decision:ImpactDecision,rule_version:str,batch_id:UUID|None=None)->UUID:
        iid=uuid4(); cursor.execute(self.INSERT,(iid,source_event_id,batch_id,decision.property_id,decision.report_id,decision.report_variant,decision.dependency_type,decision.dependency_id,decision.stored_fingerprint,decision.current_fingerprint,decision.change_class,decision.decision,decision.rule_id,rule_version,decision.reason_code,correlation_id)); row=cursor.fetchone()
        if row: return UUID(str(row[0]))
        cursor.execute(self.FIND,(source_event_id,decision.property_id,decision.report_variant,decision.dependency_type,decision.dependency_id)); existing=cursor.fetchone()
        if not existing: raise RuntimeError('impact persistence conflict without existing row')
        if str(existing[1])!=decision.decision or str(existing[2])!=decision.reason_code: raise RuntimeError('conflicting duplicate impact evaluation')
        return UUID(str(existing[0]))
