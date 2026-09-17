from __future__ import annotations

import json
from datetime import datetime
from uuid import UUID

from .models import ProcessedCommand


class ProcessedCommandRepository:
    SELECT_SQL = '''SELECT command_id,service_name,command_type,idempotency_key,request_hash,result_status,result_payload,processed_at,correlation_id
    FROM audit.processed_commands WHERE service_name=%s AND idempotency_key=%s'''

    INSERT_SQL = '''INSERT INTO audit.processed_commands
    (command_id,service_name,command_type,idempotency_key,request_hash,result_status,result_payload,correlation_id)
    VALUES (%s,%s,%s,%s,%s,%s,%s::jsonb,%s)'''

    def get(self, cursor, service_name: str, idempotency_key: str) -> ProcessedCommand | None:
        cursor.execute(self.SELECT_SQL, (service_name, idempotency_key))
        row = cursor.fetchone()
        if row is None:
            return None
        payload = row[6]
        if isinstance(payload, str):
            payload = json.loads(payload)
        return ProcessedCommand(
            command_id=UUID(str(row[0])),
            service_name=row[1],
            command_type=row[2],
            idempotency_key=row[3],
            request_hash=row[4],
            result_status=row[5],
            result_payload=payload,
            processed_at=row[7] if isinstance(row[7], datetime) else None,
            correlation_id=UUID(str(row[8])),
        )

    def insert(self, cursor, command: ProcessedCommand) -> None:
        cursor.execute(
            self.INSERT_SQL,
            (
                command.command_id,
                command.service_name,
                command.command_type,
                command.idempotency_key,
                command.request_hash,
                command.result_status,
                json.dumps(command.result_payload, separators=(',', ':'), sort_keys=True),
                command.correlation_id,
            ),
        )
