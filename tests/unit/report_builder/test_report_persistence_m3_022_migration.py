from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]

def test_config_dependencies_may_be_non_snapshot_owned():
    sql=(ROOT/'database/migrations/0034_report_dependency_source_scope.sql').read_text()
    assert 'source_snapshot_id DROP NOT NULL' in sql
