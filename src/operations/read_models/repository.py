class OperationsReadModelRepository:
    PROPERTY_HEALTH_SQL = '''SELECT property_id,health_status,current_snapshot_id,open_job_count,pointer_violation_count,orphan_count,stuck_job_count,release_failure_count FROM operations.property_health_current WHERE property_id=%s'''
    FLEET_HEALTH_SQL = '''SELECT total_properties,healthy_count,degraded_count,critical_count,unknown_count,open_job_count,active_release_count FROM operations.fleet_health_current'''
    def get_property_health(self,cursor,property_id):
        cursor.execute(self.PROPERTY_HEALTH_SQL,(property_id,)); return cursor.fetchone()
    def get_fleet_health(self,cursor):
        cursor.execute(self.FLEET_HEALTH_SQL); return cursor.fetchone()
