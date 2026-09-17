from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]

def read(name): return (ROOT/'database'/'migrations'/name).read_text()

def test_render_parent_and_dependency_tables_exist():
    s = read('0040_render_tables.sql')
    assert 'CREATE TABLE IF NOT EXISTS reporting.render_versions' in s
    assert 'REFERENCES reporting.report_versions(report_id)' in s
    assert 'CREATE TABLE IF NOT EXISTS reporting.render_dependencies' in s
    assert 'REFERENCES reporting.render_versions(render_id)' in s

def test_render_identity_and_dedupe_constraints_are_structural():
    s = read('0040_render_tables.sql')
    assert 'UNIQUE(report_id, render_type, render_version)' in s
    assert 'UNIQUE(report_id, render_type, presentation_input_hash)' in s
    assert "presentation_input_hash ~ '^[0-9a-f]{64}$'" in s

def test_render_artifact_is_not_required_before_generation_completes():
    s = read('0040_render_tables.sql')
    assert 'artifact_hash char(64) NULL' in s
    assert 'storage_uri text NULL' in s
    assert 'mime_type text NULL' in s

def test_render_reverse_dependency_index_exists():
    s = read('0041_render_indexes.sql')
    assert 'idx_render_dependencies_reverse' in s

def test_render_migrations_do_not_cascade_delete_history():
    for name in ['0040_render_tables.sql','0041_render_indexes.sql']:
        assert 'ON DELETE CASCADE' not in read(name).upper()
