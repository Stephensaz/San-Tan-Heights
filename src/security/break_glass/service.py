from datetime import timedelta, datetime
from uuid import uuid4, UUID
from .models import BreakGlassGrant
class BreakGlassDenied(PermissionError): pass
class BreakGlassService:
    def __init__(self, policy): self.policy=policy
    def issue(self, *, issuer_role:str, principal_id:str, issued_by:str, incident_id:UUID|None, reason_code:str, actions, property_ids, now:datetime, duration_minutes:int):
        if issuer_role not in self.policy.issuer_roles: raise BreakGlassDenied('issuer role not authorized')
        if incident_id is None or not reason_code: raise BreakGlassDenied('incident and reason required')
        actions=tuple(sorted(set(actions or ())))
        if not actions: raise BreakGlassDenied('explicit actions required')
        if set(actions)&self.policy.prohibited_actions: raise BreakGlassDenied('break-glass cannot grant break-glass administration')
        if duration_minutes<=0 or duration_minutes>self.policy.max_duration_minutes: raise BreakGlassDenied('duration exceeds policy')
        return BreakGlassGrant(uuid4(),principal_id,issued_by,incident_id,reason_code,actions,tuple(sorted(set(property_ids or ()))),now,now+timedelta(minutes=duration_minutes))
    def require(self, grant:BreakGlassGrant, *, action:str, property_id:str|None, now:datetime):
        if not grant.is_active(now): raise BreakGlassDenied('break-glass grant inactive')
        if action not in grant.actions: raise BreakGlassDenied('action not granted')
        if grant.property_ids and (property_id is None or property_id not in grant.property_ids): raise BreakGlassDenied('property not granted')
        return grant
