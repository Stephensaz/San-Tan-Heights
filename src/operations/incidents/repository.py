from __future__ import annotations
from .models import Incident

class IncidentRepository:
    INSERT='''INSERT INTO operations.incidents
(incident_id,incident_key,incident_type,severity,incident_state,source_rule_id,source_entity_type,source_entity_id,property_id,report_variant,channel,release_id,reason_code,correlation_id)
VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
ON CONFLICT(incident_key) DO NOTHING RETURNING incident_id'''
    GET_KEY='''SELECT incident_id,incident_key,incident_type,severity,incident_state,reason_code,property_id,report_variant,channel,release_id,source_rule_id,source_entity_type,source_entity_id,correlation_id
FROM operations.incidents WHERE incident_key=%s'''
    UPDATE_STATE='''UPDATE operations.incidents SET incident_state=%s,
contained_at=CASE WHEN %s='CONTAINED' THEN COALESCE(contained_at,now()) ELSE contained_at END,
resolved_at=CASE WHEN %s='RESOLVED' THEN COALESCE(resolved_at,now()) ELSE resolved_at END,
closed_at=CASE WHEN %s='CLOSED' THEN COALESCE(closed_at,now()) ELSE closed_at END,
updated_at=now() WHERE incident_id=%s AND incident_state=%s'''
    HISTORY='''INSERT INTO operations.incident_history(incident_id,from_state,to_state,reason_code,actor,correlation_id) VALUES (%s,%s,%s,%s,%s,%s)'''
    def create(self,cursor,incident:Incident):
        cursor.execute(self.INSERT,(incident.incident_id,incident.incident_key,incident.incident_type,incident.severity,incident.incident_state,incident.source_rule_id,incident.source_entity_type,incident.source_entity_id,incident.property_id,incident.report_variant,incident.channel,incident.release_id,incident.reason_code,incident.correlation_id))
        return cursor.fetchone()
    def update_state(self,cursor,incident:Incident,to_state:str,reason_code:str,actor:str):
        cursor.execute(self.UPDATE_STATE,(to_state,to_state,to_state,to_state,incident.incident_id,incident.incident_state))
        if getattr(cursor,'rowcount',1)!=1: raise RuntimeError('incident state changed concurrently')
        cursor.execute(self.HISTORY,(incident.incident_id,incident.incident_state,to_state,reason_code,actor,incident.correlation_id))
