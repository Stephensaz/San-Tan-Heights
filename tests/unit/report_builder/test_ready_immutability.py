from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
def test_ready_semantic_immutability_migration_protects_payload_and_dependencies():
    sql=(ROOT/'database/migrations/0035_ready_semantic_immutability.sql').read_text()
    assert "OLD.content_state = 'READY'" in sql
    for field in ('canonical_payload','report_input_hash','canonical_payload_hash','dependency_manifest_hash','snapshot_id','version_number'):
        assert field in sql
    assert 'READY_REPORT_DEPENDENCIES_IMMUTABLE' in sql
    assert 'BEFORE UPDATE OR DELETE ON reporting.report_dependencies' in sql
