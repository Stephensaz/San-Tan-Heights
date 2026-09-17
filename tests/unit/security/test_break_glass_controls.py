from datetime import datetime, timezone, timedelta
from pathlib import Path
from uuid import uuid4
import pytest
from src.security.break_glass import BreakGlassPolicyRegistry,BreakGlassService,BreakGlassDenied
ROOT=Path(__file__).resolve().parents[3]
def test_break_glass_is_bounded_scoped_and_expiring():
    s=BreakGlassService(BreakGlassPolicyRegistry.from_repository(ROOT)); now=datetime.now(timezone.utc); pid=str(uuid4())
    g=s.issue(issuer_role='ADMIN',principal_id='ops-1',issued_by='admin-1',incident_id=uuid4(),reason_code='SECURITY_INCIDENT',actions=['publication.manage'],property_ids=[pid],now=now,duration_minutes=30)
    assert s.require(g,action='publication.manage',property_id=pid,now=now) is g
    with pytest.raises(BreakGlassDenied): s.require(g,action='publication.manage',property_id=pid,now=now+timedelta(minutes=31))
def test_break_glass_cannot_delegate_or_be_issued_by_operations():
    s=BreakGlassService(BreakGlassPolicyRegistry.from_repository(ROOT)); now=datetime.now(timezone.utc)
    with pytest.raises(BreakGlassDenied): s.issue(issuer_role='OPERATIONS',principal_id='x',issued_by='x',incident_id=uuid4(),reason_code='R',actions=['publication.manage'],property_ids=[],now=now,duration_minutes=10)
    with pytest.raises(BreakGlassDenied): s.issue(issuer_role='ADMIN',principal_id='x',issued_by='x',incident_id=uuid4(),reason_code='R',actions=['security.break_glass.delegate'],property_ids=[],now=now,duration_minutes=10)
