from dataclasses import dataclass
@dataclass(frozen=True)
class OperationsDashboard:
    fleet_status:str
    total_properties:int
    healthy_count:int
    degraded_count:int
    critical_count:int
    unknown_count:int
    open_job_count:int
    active_release_count:int
    open_incident_count:int
    critical_incident_count:int
    active_global_publication_freeze:bool
    latest_backup_status:str|None
    latest_restore_status:str|None
