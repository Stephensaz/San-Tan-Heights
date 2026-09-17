from __future__ import annotations
import json
from .models import OrchestrationEvent, StateTransitionRecord, GuardEvaluationRecord

class AppendOnlyRepositoryError(RuntimeError):
    pass

class EventRepository:
    SQL = '''INSERT INTO audit.orchestration_events
    (event_id,event_type,event_version,occurred_at,property_id,report_id,snapshot_id,job_id,release_id,correlation_id,causation_event_id,actor_type,actor_id,source_system,reason_code,payload,payload_hash)
    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s)'''
    def insert(self, cursor, event: OrchestrationEvent) -> None:
        cursor.execute(self.SQL, (event.event_id,event.event_type,event.event_version,event.occurred_at,event.property_id,event.report_id,event.snapshot_id,event.job_id,event.release_id,event.correlation_id,event.causation_event_id,event.actor_type,event.actor_id,event.source_system,event.reason_code,json.dumps(event.payload,separators=(',',':'),sort_keys=True),event.payload_hash))

class TransitionRepository:
    SQL = '''INSERT INTO audit.state_transitions
    (transition_record_id,transition_id,entity_type,entity_id,state_dimension,from_state,to_state,result,reason_code,event_id,correlation_id,actor_type,actor_id)
    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)'''
    def insert(self, cursor, record: StateTransitionRecord) -> None:
        cursor.execute(self.SQL, (record.transition_record_id,record.transition_id,record.entity_type,record.entity_id,record.state_dimension,record.from_state,record.to_state,record.result,record.reason_code,record.event_id,record.correlation_id,record.actor_type,record.actor_id))

class GuardRepository:
    SQL = '''INSERT INTO audit.guard_evaluations
    (guard_evaluation_id,transition_record_id,guard_id,ordinal,result,reason_code,safe_details,correlation_id)
    VALUES (%s,%s,%s,%s,%s,%s,%s::jsonb,%s)'''
    def insert(self, cursor, record: GuardEvaluationRecord) -> None:
        cursor.execute(self.SQL, (record.guard_evaluation_id,record.transition_record_id,record.guard_id,record.ordinal,record.result,record.reason_code,json.dumps(record.safe_details,separators=(',',':'),sort_keys=True),record.correlation_id))
