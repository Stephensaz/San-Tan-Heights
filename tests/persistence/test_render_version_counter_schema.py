from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]

def test_render_version_counter_is_keyed_by_report_and_type():
    s=(ROOT/'database/migrations/0042_render_version_counters.sql').read_text()
    assert 'CREATE TABLE IF NOT EXISTS reporting.render_version_counters' in s
    assert 'PRIMARY KEY(report_id, render_type)' in s
    assert 'REFERENCES reporting.report_versions(report_id)' in s
    assert 'MAX(' not in s.upper()
