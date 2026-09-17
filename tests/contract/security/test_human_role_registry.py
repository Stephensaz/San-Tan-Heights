from pathlib import Path
from src.security.authorization import HumanRoleRegistry
ROOT=Path(__file__).resolve().parents[3]

def test_locked_human_roles_match_security_contract_and_agent_is_not_admin():
    r=HumanRoleRegistry.from_repository(ROOT)
    assert set(r.role_ids)=={'PUBLIC','SELLER','AGENT','OPERATIONS','ADMIN'}
    assert r.get('AGENT').property_scope_mode=='ASSIGNED'
    assert r.get('OPERATIONS').property_scope_mode=='FLEET'
    assert 'RESTRICTED' not in r.get('AGENT').classifications
    assert r.get('ADMIN').actions==frozenset({'*'})

def test_public_is_limited_to_sanitized_current_publication_action():
    r=HumanRoleRegistry.from_repository(ROOT)
    assert r.get('PUBLIC').actions==frozenset({'publication.current_public.read'})
    assert r.get('PUBLIC').classifications==frozenset({'PUBLIC_DATA'})
