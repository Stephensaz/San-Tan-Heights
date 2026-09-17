from __future__ import annotations
from .models import OperationsDashboard
class OperationsDashboardProjector:
    """Read-only operational projection; never authoritative and never mutates source state."""
    SQL='''SELECT fleet_status,total_properties,healthy_count,degraded_count,critical_count,unknown_count,open_job_count,active_release_count,open_incident_count,critical_incident_count,active_global_publication_freeze,latest_backup_status,latest_restore_status FROM operations.operations_dashboard_current'''
    def read(self,cursor):
        cursor.execute(self.SQL); row=cursor.fetchone()
        if not row:return None
        return OperationsDashboard(*row)
