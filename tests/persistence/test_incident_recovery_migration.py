from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
def test_incident_recovery_persistence_is_durable_and_idempotent():
    s=(ROOT/'database/migrations/0084_incident_recovery_control.sql').read_text()
    for name in ['operations.incidents','operations.incident_history','operations.containment_actions','operations.recovery_commands','operations.recovery_command_history']:
        assert name in s
    assert 'UNIQUE(incident_id,idempotency_key)' in s
    assert "incident_state IN ('OPEN','CONTAINED','RECOVERING')" in s

def test_incident_reason_codes_are_additively_seeded():
    s=(ROOT/'database/migrations/0167_reference_seed_data.sql').read_text()
    assert 'INCIDENT_DETECTED' in s and 'RECOVERY_COMMAND_REQUESTED' in s and 'INCIDENT_RECOVERED' in s
