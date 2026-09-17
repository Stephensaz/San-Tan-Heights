from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]

def text(name): return (ROOT/'database'/'migrations'/name).read_text()

def test_report_tables_have_semantic_uniqueness():
    s=text('0030_report_tables.sql')
    assert 'UNIQUE(property_id, report_variant, version_number)' in s
    assert 'UNIQUE(property_id, report_variant, report_input_hash)' in s
    assert 'reporting.report_dependencies' in s

def test_report_indexes_include_reverse_dependency():
    assert 'idx_report_dependencies_reverse' in text('0031_report_indexes.sql')

def test_ready_requires_pass_qa():
    s=text('0032_report_extensions.sql')
    assert "content_state <> 'READY'" in s
    assert "qa_status='PASS'" in s

def test_version_counter_primary_key_and_no_max():
    s=text('0033_report_version_counters.sql')
    assert 'PRIMARY KEY(property_id, report_variant)' in s
    assert 'MAX(' not in s.upper()
