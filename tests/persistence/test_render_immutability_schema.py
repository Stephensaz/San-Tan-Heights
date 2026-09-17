from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]

def test_ready_render_artifact_immutability_trigger_exists():
    sql=(ROOT/'database/migrations/0043_render_ready_immutability.sql').read_text()
    assert 'READY_RENDER_ARTIFACT_IMMUTABLE' in sql
    for field in ['artifact_hash','artifact_size_bytes','storage_uri','presentation_input_hash','template_version','renderer_version']:
        assert field in sql

def test_ready_render_dependencies_are_immutable():
    sql=(ROOT/'database/migrations/0043_render_ready_immutability.sql').read_text()
    assert 'READY_RENDER_DEPENDENCIES_IMMUTABLE' in sql
    assert 'BEFORE UPDATE OR DELETE ON reporting.render_dependencies' in sql

def test_ready_render_requires_complete_clean_passed_artifact():
    sql=(ROOT/'database/migrations/0044_render_integrity_constraints.sql').read_text()
    assert 'ck_ready_render_artifact_complete' in sql
    assert "health_state = 'CLEAN'" in sql and "qa_status = 'PASS'" in sql and 'publication_eligible = true' in sql
