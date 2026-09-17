class SecurityAuditRepository:
    def insert(self, cur, e):
        cur.execute('''INSERT INTO audit.security_events
        (security_event_id,event_type,occurred_at,actor_type,actor_id,outcome,reason_code,property_id,incident_id,correlation_id,evidence_hash)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)''',(e.security_event_id,e.event_type,e.occurred_at,e.actor_type,e.actor_id,e.outcome,e.reason_code,e.property_id,e.incident_id,e.correlation_id,e.evidence_hash))
