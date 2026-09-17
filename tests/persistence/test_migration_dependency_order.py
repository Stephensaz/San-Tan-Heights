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
