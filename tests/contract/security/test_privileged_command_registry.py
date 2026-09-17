from pathlib import Path
from src.security.privileged import PrivilegedCommandRegistry
ROOT=Path(__file__).resolve().parents[3]
def test_privileged_command_registry_is_locked_and_complete_for_recovery_commands():
    r=PrivilegedCommandRegistry.from_repository(ROOT)
    assert r.registry_id=='STH-PRIVILEGED-COMMAND-POLICY-v1.0'
    for cmd in ['RELEASE_PUBLICATION_FREEZE','REQUEUE_REGENERATION_JOB','RETRY_RELEASE_ITEM','REVALIDATE_PUBLICATION_TARGET','RESOLVE_INCIDENT']:
        assert r.get(cmd).required_action=='recovery.execute'
