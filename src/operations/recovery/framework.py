from __future__ import annotations
from dataclasses import dataclass
import json
from uuid import UUID,uuid4
from src.shared.hash import sha256_canonical

@dataclass(frozen=True)
class RecoveryResult:
    status:str
    command_id:UUID
    detail:dict

class RecoveryCommandFramework:
    SELECT='''SELECT recovery_command_id,request_hash,command_status,result_json FROM operations.recovery_commands WHERE incident_id=%s AND idempotency_key=%s'''
    INSERT='''INSERT INTO operations.recovery_commands(recovery_command_id,incident_id,idempotency_key,command_type,request_hash,command_status,command_payload,reason_code,requested_by,correlation_id)
VALUES (%s,%s,%s,%s,%s,'REQUESTED',%s::jsonb,%s,%s,%s)'''
    STATUS='''UPDATE operations.recovery_commands SET command_status=%s,result_json=%s::jsonb,started_at=COALESCE(started_at,now()),completed_at=CASE WHEN %s IN ('SUCCEEDED','FAILED','BLOCKED','NO_OP') THEN now() ELSE completed_at END WHERE recovery_command_id=%s'''
    HISTORY='''INSERT INTO operations.recovery_command_history(recovery_command_id,from_status,to_status,reason_code,actor,detail_json) VALUES (%s,%s,%s,%s,%s,%s::jsonb)'''
    def __init__(self,registry,actions): self.registry=registry; self.actions=actions
    def execute(self,cursor,*,incident,command_type,payload,idempotency_key,requested_by,reason_code='RECOVERY_COMMAND_REQUESTED'):
        self.registry.validate(command_type,payload,incident.incident_state)
        req={'incident_id':str(incident.incident_id),'command_type':command_type,'payload':payload}
        request_hash=sha256_canonical(req)
        cursor.execute(self.SELECT,(incident.incident_id,idempotency_key)); row=cursor.fetchone()
        if row:
            if row[1]!=request_hash: raise ValueError('recovery idempotency key reused with different request')
            detail=row[3] if isinstance(row[3],dict) else {}
            return RecoveryResult(row[2],UUID(str(row[0])),detail or {})
        command_id=uuid4(); payload_json=json.dumps(payload,sort_keys=True,separators=(',',':'))
        cursor.execute(self.INSERT,(command_id,incident.incident_id,idempotency_key,command_type,request_hash,payload_json,reason_code,requested_by,incident.correlation_id))
        cursor.execute(self.HISTORY,(command_id,None,'REQUESTED',reason_code,requested_by,'{}'))
        cursor.execute(self.STATUS,('RUNNING','{}','RUNNING',command_id)); cursor.execute(self.HISTORY,(command_id,'REQUESTED','RUNNING',reason_code,requested_by,'{}'))
        try:
            action_result=self.actions.execute(cursor,incident=incident,command_type=command_type,payload=payload,actor=requested_by)
            status=action_result.get('status','SUCCEEDED'); status=status if status in {'SUCCEEDED','FAILED','BLOCKED','NO_OP'} else 'SUCCEEDED'
            result_json=json.dumps(action_result,sort_keys=True,separators=(',',':'))
            cursor.execute(self.STATUS,(status,result_json,status,command_id)); cursor.execute(self.HISTORY,(command_id,'RUNNING',status,reason_code,requested_by,result_json))
            return RecoveryResult(status,command_id,action_result)
        except Exception as exc:
            detail={'error_type':type(exc).__name__}
            result_json=json.dumps(detail,sort_keys=True,separators=(',',':'))
            cursor.execute(self.STATUS,('FAILED',result_json,'FAILED',command_id)); cursor.execute(self.HISTORY,(command_id,'RUNNING','FAILED','RECOVERY_ACTION_FAILED',requested_by,result_json))
            raise
