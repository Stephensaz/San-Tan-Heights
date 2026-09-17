from pathlib import Path

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
