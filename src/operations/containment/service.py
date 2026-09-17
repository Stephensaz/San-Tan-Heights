from __future__ import annotations
from dataclasses import dataclass
from uuid import uuid4

@dataclass(frozen=True)
class ContainmentDecision:
    status:str
    action_type:str|None=None
    reason_code:str|None=None

class AutomaticContainment:
    INSERT='''INSERT INTO operations.containment_actions(containment_action_id,incident_id,action_type,target_key,action_status,reason_code,evidence_json,applied_by,correlation_id,applied_at)
VALUES (%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s,CASE WHEN %s IN ('APPLIED','NO_OP') THEN now() ELSE NULL END)
ON CONFLICT(incident_id,action_type,target_key) DO NOTHING'''
    def __init__(self,registry,freeze_repository=None,release_lifecycle=None): self.registry=registry; self.freezes=freeze_repository; self.releases=release_lifecycle
    def contain(self,cursor,*,incident,target_key,actor='OPERATIONS_SERVICE',evidence_json='{}'):
        rule=self.registry.resolve(incident.incident_type,incident.severity)
        if rule is None:return ContainmentDecision('NO_ACTION')
        action=rule['action_type']; status='APPLIED'
        if action=='FREEZE_PUBLICATION_TARGET':
            if not (incident.property_id and incident.report_variant): status='FAILED'
            elif self.freezes:
                from src.publication.freeze.repository import PublicationFreeze
                self.freezes.create(cursor,PublicationFreeze(uuid4(),incident.property_id,incident.report_variant,incident.channel,rule['reason_code'],actor))
        elif action=='BLOCK_RELEASE':
            if not incident.release_id: status='FAILED'
        elif action=='HOLD_REGENERATION_TARGET':
            if not incident.property_id: status='FAILED'
        cursor.execute(self.INSERT,(uuid4(),incident.incident_id,action,target_key,status,rule['reason_code'],evidence_json,actor,incident.correlation_id,status))
        return ContainmentDecision(status,action,rule['reason_code'])
