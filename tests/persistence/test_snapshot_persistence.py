from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
def read(name): return (ROOT/'database/migrations'/name).read_text()
def test_snapshot_tables_and_property_anchor_exist():
    assert 'CREATE TABLE IF NOT EXISTS core.properties' in read('0010_core_properties.sql')
    t=read('0020_snapshot_tables.sql')
    for table in ['snapshot.intelligence_snapshots','snapshot.snapshot_findings','snapshot.snapshot_dependencies']:
        assert f'CREATE TABLE IF NOT EXISTS {table}' in t
    assert 'REFERENCES core.properties(property_id)' in t

def test_snapshot_support_tables_exist():
    assert 'snapshot.snapshot_requirement_results' in read('0200_snapshot_requirement_results.sql')
    assert 'snapshot.snapshot_diffs' in read('0201_snapshot_diffs.sql')

def test_snapshot_children_are_immutable():
    t=read('0202_snapshot_immutability.sql')
    for table in ['snapshot.snapshot_findings','snapshot.snapshot_dependencies','snapshot.snapshot_requirement_results','snapshot.snapshot_diffs']:
        assert f'ON {table}' in t
    assert 'BEFORE UPDATE OR DELETE' in t

def test_no_cascade_delete_in_snapshot_migrations():
    for n in ['0010_core_properties.sql','0020_snapshot_tables.sql','0200_snapshot_requirement_results.sql','0201_snapshot_diffs.sql','0202_snapshot_immutability.sql']:
        assert 'ON DELETE CASCADE' not in read(n).upper()

def test_accepted_snapshot_semantics_are_immutable():
    t=read('0203_snapshot_parent_immutability.sql')
    assert "OLD.qa_status = 'PASS'" in t
    assert 'accepted snapshot semantic fields are immutable' in t
