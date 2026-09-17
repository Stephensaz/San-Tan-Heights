from __future__ import annotations
from .models import IncidentTransition
from .repository import IncidentRepository

TRANSITIONS={
 'OPEN':{'CONTAINED','RECOVERING','RESOLVED'},
 'CONTAINED':{'RECOVERING','RESOLVED'},
 'RECOVERING':{'CONTAINED','RESOLVED'},
 'RESOLVED':{'CLOSED','OPEN'},
 'CLOSED':set(),
}
class IncidentLifecycle:
    def __init__(self,repository=None): self.repository=repository or IncidentRepository()
    def transition(self,cursor,*,incident,to_state,reason_code,actor='OPERATIONS_SERVICE'):
        if to_state not in TRANSITIONS.get(incident.incident_state,set()):
            raise ValueError(f'illegal incident transition {incident.incident_state}->{to_state}')
        self.repository.update_state(cursor,incident,to_state,reason_code,actor)
        return IncidentTransition('TRANSITIONED',incident.incident_state,to_state)
