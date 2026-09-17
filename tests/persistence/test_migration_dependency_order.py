from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
MIGRATIONS = ROOT / 'database' / 'migrations'


def test_immutability_function_exists_before_first_trigger_reference():
    files = sorted(MIGRATIONS.glob('*.sql'), key=lambda p: p.name)
    creator_indexes = []
    consumer_indexes = []
    for index, path in enumerate(files):
        sql = path.read_text()
        if 'CREATE OR REPLACE FUNCTION audit.prevent_immutable_mutation()' in sql:
            creator_indexes.append(index)
        if 'EXECUTE FUNCTION audit.prevent_immutable_mutation()' in sql:
            consumer_indexes.append(index)

    assert creator_indexes, 'immutability trigger function has no migration creator'
    assert consumer_indexes, 'immutability trigger function has no migration consumers'
    assert min(creator_indexes) < min(consumer_indexes), (
        'audit.prevent_immutable_mutation() must be created before any trigger references it'
    )


def test_orchestration_events_exists_before_first_foreign_key_reference():
    files = sorted(MIGRATIONS.glob('*.sql'), key=lambda p: p.name)
    creator_indexes = []
    consumer_indexes = []
    create_marker = 'CREATE TABLE IF NOT EXISTS audit.orchestration_events'
    reference_marker = 'REFERENCES audit.orchestration_events(event_id)'

    for index, path in enumerate(files):
        sql = path.read_text()
        if create_marker in sql:
            creator_indexes.append(index)
        if reference_marker in sql and create_marker not in sql:
            consumer_indexes.append(index)

    assert creator_indexes, 'audit.orchestration_events has no migration creator'
    assert consumer_indexes, 'audit.orchestration_events has no migration consumers'
    assert min(creator_indexes) < min(consumer_indexes), (
        'audit.orchestration_events must be created before any migration references it'
    )


def test_current_snapshot_view_exists_before_first_consumer():
    files = sorted(MIGRATIONS.glob('*.sql'), key=lambda p: p.name)
    creator_indexes = []
    consumer_indexes = []
    create_marker = 'CREATE OR REPLACE VIEW snapshot.current_snapshot_view AS'
    reference_marker = 'snapshot.current_snapshot_view'

    for index, path in enumerate(files):
        sql = path.read_text()
        if create_marker in sql:
            creator_indexes.append(index)
        if reference_marker in sql and create_marker not in sql:
            consumer_indexes.append(index)

    assert creator_indexes, 'snapshot.current_snapshot_view has no migration creator'
    assert consumer_indexes, 'snapshot.current_snapshot_view has no migration consumers'
    assert min(creator_indexes) < min(consumer_indexes), (
        'snapshot.current_snapshot_view must be created before any migration consumes it'
    )


def test_shared_immutable_row_function_exists_before_first_trigger_reference():
    files = sorted(MIGRATIONS.glob('*.sql'), key=lambda p: p.name)
    creator_indexes = []
    consumer_indexes = []
    create_marker = 'CREATE OR REPLACE FUNCTION shared.raise_immutable_row()'
    reference_marker = 'EXECUTE FUNCTION shared.raise_immutable_row()'

    for index, path in enumerate(files):
        sql = path.read_text()
        if create_marker in sql:
            creator_indexes.append(index)
        if reference_marker in sql:
            consumer_indexes.append(index)

    assert creator_indexes, 'shared.raise_immutable_row() has no migration creator'
    assert consumer_indexes, 'shared.raise_immutable_row() has no migration consumers'
    assert min(creator_indexes) < min(consumer_indexes), (
        'shared.raise_immutable_row() must be created before any trigger references it'
    )


def test_snapshot_requirement_results_exists_before_first_grant_reference():
    files = sorted(MIGRATIONS.glob('*.sql'), key=lambda p: p.name)
    creator_indexes = []
    consumer_indexes = []
    create_marker = 'CREATE TABLE IF NOT EXISTS snapshot.snapshot_requirement_results'
    grant_marker = 'snapshot.snapshot_requirement_results'

    for index, path in enumerate(files):
        sql = path.read_text()
        if create_marker in sql:
            creator_indexes.append(index)
        if grant_marker in sql and create_marker not in sql and 'GRANT ' in sql:
            consumer_indexes.append(index)

    assert creator_indexes, 'snapshot.snapshot_requirement_results has no migration creator'
    assert consumer_indexes, 'snapshot.snapshot_requirement_results has no grant consumer'
    assert min(creator_indexes) < min(consumer_indexes), (
        'snapshot.snapshot_requirement_results must be created before any migration grants it'
    )


def test_late_grant_objects_exist_before_first_grant_reference():
    files = sorted(MIGRATIONS.glob('*.sql'), key=lambda p: p.name)
    objects = (
        ('snapshot.snapshot_diffs', 'CREATE TABLE IF NOT EXISTS snapshot.snapshot_diffs'),
        ('snapshot.snapshot_sequence_counters', 'CREATE TABLE IF NOT EXISTS snapshot.snapshot_sequence_counters'),
        ('reporting.report_diffs', 'CREATE TABLE IF NOT EXISTS reporting.report_diffs'),
    )

    for object_name, create_marker in objects:
        creator_indexes = []
        consumer_indexes = []
        for index, path in enumerate(files):
            sql = path.read_text()
            if create_marker in sql:
                creator_indexes.append(index)
            if object_name in sql and create_marker not in sql and 'GRANT ' in sql:
                consumer_indexes.append(index)

        assert creator_indexes, f'{object_name} has no migration creator'
        assert consumer_indexes, f'{object_name} has no grant consumer'
        assert min(creator_indexes) < min(consumer_indexes), (
            f'{object_name} must be created before any migration grants it'
        )


def test_event_type_seed_inserts_always_include_version():
    bad = []
    insert_pattern = re.compile(r'INSERT\s+INTO\s+reference\.event_type\s*\(([^)]*)\)', re.IGNORECASE)

    for path in sorted(MIGRATIONS.glob('*.sql'), key=lambda p: p.name):
        sql = path.read_text()
        for match in insert_pattern.finditer(sql):
            columns = {column.strip().lower() for column in match.group(1).split(',')}
            if 'version' not in columns:
                bad.append(path.name)

    assert not bad, f'reference.event_type seed inserts must include required version column: {bad}'
