from __future__ import annotations

from datetime import timedelta
from uuid import UUID

from .models import EventConsumption, OutboxMessage


class OutboxRepository:
    INSERT_SQL = '''INSERT INTO audit.event_outbox (event_id,topic) VALUES (%s,%s)
    ON CONFLICT (event_id,topic) DO NOTHING'''

    CLAIM_SQL = '''WITH next_rows AS (
      SELECT outbox_id
      FROM audit.event_outbox
      WHERE delivery_state IN ('PENDING','RETRY')
        AND (next_attempt_at IS NULL OR next_attempt_at <= now())
      ORDER BY created_at ASC, outbox_id ASC
      FOR UPDATE SKIP LOCKED
      LIMIT %s
    )
    UPDATE audit.event_outbox o
    SET delivery_state='CLAIMED', claimed_at=now(), claimed_by=%s,
        lease_expires_at=now() + (%s * interval '1 second')
    FROM next_rows n
    WHERE o.outbox_id=n.outbox_id
    RETURNING o.outbox_id,o.event_id,o.topic,o.delivery_state,o.attempt_count,o.claimed_by,o.lease_expires_at'''

    MARK_DELIVERED_SQL = '''UPDATE audit.event_outbox
    SET delivery_state='DELIVERED', delivered_at=now(), lease_expires_at=NULL,
        last_error_code=NULL,last_error_safe=NULL
    WHERE outbox_id=%s AND delivery_state='CLAIMED' AND claimed_by=%s'''

    MARK_RETRY_SQL = '''UPDATE audit.event_outbox
    SET delivery_state=CASE WHEN attempt_count + 1 >= %s THEN 'DEAD_LETTER' ELSE 'RETRY' END,
        attempt_count=attempt_count + 1,
        next_attempt_at=CASE WHEN attempt_count + 1 >= %s THEN NULL ELSE now() + (%s * interval '1 second') END,
        lease_expires_at=NULL,
        claimed_by=NULL,
        last_error_code=%s,
        last_error_safe=%s
    WHERE outbox_id=%s AND delivery_state='CLAIMED' AND claimed_by=%s'''

    RECLAIM_EXPIRED_SQL = '''UPDATE audit.event_outbox
    SET delivery_state='RETRY', claimed_by=NULL, lease_expires_at=NULL,
        next_attempt_at=now(), last_error_code='LEASE_EXPIRED',
        last_error_safe='Outbox delivery lease expired before completion.'
    WHERE delivery_state='CLAIMED' AND lease_expires_at < now()'''

    def insert(self, cursor, event_id: UUID, topic: str) -> None:
        cursor.execute(self.INSERT_SQL, (event_id, topic))

    def claim(self, cursor, worker_id: str, limit: int = 50, lease_seconds: int = 60) -> list[OutboxMessage]:
        if limit < 1:
            raise ValueError('limit must be >= 1')
        if lease_seconds < 1:
            raise ValueError('lease_seconds must be >= 1')
        cursor.execute(self.CLAIM_SQL, (limit, worker_id, lease_seconds))
        rows = cursor.fetchall()
        return [
            OutboxMessage(
                outbox_id=UUID(str(r[0])), event_id=UUID(str(r[1])), topic=r[2],
                delivery_state=r[3], attempt_count=r[4], claimed_by=r[5], lease_expires_at=r[6]
            )
            for r in rows
        ]

    def mark_delivered(self, cursor, outbox_id: UUID, worker_id: str) -> None:
        cursor.execute(self.MARK_DELIVERED_SQL, (outbox_id, worker_id))

    def mark_retry(self, cursor, outbox_id: UUID, worker_id: str, error_code: str,
                   safe_error: str, max_attempts: int = 5, retry_seconds: int = 30) -> None:
        cursor.execute(self.MARK_RETRY_SQL, (
            max_attempts, max_attempts, retry_seconds, error_code, safe_error[:1000], outbox_id, worker_id
        ))

    def reclaim_expired(self, cursor) -> None:
        cursor.execute(self.RECLAIM_EXPIRED_SQL)


class EventConsumptionRepository:
    EXISTS_SQL = '''SELECT 1 FROM audit.event_consumptions WHERE consumer_name=%s AND event_id=%s'''
    INSERT_SQL = '''INSERT INTO audit.event_consumptions (consumer_name,event_id,result_hash)
    VALUES (%s,%s,%s) ON CONFLICT (consumer_name,event_id) DO NOTHING'''

    def has_consumed(self, cursor, consumer_name: str, event_id: UUID) -> bool:
        cursor.execute(self.EXISTS_SQL, (consumer_name, event_id))
        return cursor.fetchone() is not None

    def record(self, cursor, consumption: EventConsumption) -> None:
        cursor.execute(self.INSERT_SQL, (consumption.consumer_name, consumption.event_id, consumption.result_hash))
