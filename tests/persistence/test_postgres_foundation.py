from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]

def test_foundation_migrations_exist_and_are_transactional():
    for name in ["0001_extensions.sql", "0002_reference_tables.sql"]:
        text=(ROOT/"database/migrations"/name).read_text().upper()
        assert "BEGIN;" in text
        assert "COMMIT;" in text

def test_all_required_schemas_created():
    text=(ROOT/"database/migrations/0001_extensions.sql").read_text()
    for schema in ["core","snapshot","reporting","publication","orchestration","audit","operations","security","reference"]:
        assert f"CREATE SCHEMA IF NOT EXISTS {schema};" in text

def test_pgcrypto_extension_is_required():
    text=(ROOT/"database/migrations/0001_extensions.sql").read_text().lower()
    assert "create extension if not exists pgcrypto" in text

def test_reference_tables_do_not_use_native_enum_or_cascade():
    text=(ROOT/"database/migrations/0002_reference_tables.sql").read_text().upper()
    assert "CREATE TYPE" not in text
    assert "ON DELETE CASCADE" not in text
