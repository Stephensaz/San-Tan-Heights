from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
def test_migration_has_health_views_and_append_only_sweep_evidence():
    s=(ROOT/'database/migrations/0083_operations_health_and_integrity.sql').read_text()
    assert 'operations.integrity_sweep_runs' in s
    assert 'operations.integrity_findings' in s
    assert 'operations.property_health_current' in s
    assert 'operations.fleet_health_current' in s
    assert 'snapshot.current_snapshot_view' in s
