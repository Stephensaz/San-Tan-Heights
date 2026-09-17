from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SQL = (ROOT/'database'/'migrations'/'0080_release_persistence.sql').read_text()


def test_release_parent_manifest_and_item_tables_exist():
    assert 'CREATE TABLE IF NOT EXISTS operations.releases' in SQL
    assert 'CREATE TABLE IF NOT EXISTS operations.release_manifests' in SQL
    assert 'CREATE TABLE IF NOT EXISTS operations.release_items' in SQL


def test_release_parent_uses_governed_release_state():
    assert 'release_state text NOT NULL REFERENCES reference.release_state(code)' in SQL


def test_release_manifest_is_one_row_per_release_and_hash_guarded():
    assert 'release_id uuid PRIMARY KEY REFERENCES operations.releases(release_id)' in SQL
    assert "manifest_fingerprint ~ '^[0-9a-f]{64}$'" in SQL
    assert "membership_fingerprint ~ '^[0-9a-f]{64}$'" in SQL


def test_release_items_have_deterministic_membership_identity_and_no_cascade_delete():
    assert 'UNIQUE(release_id, membership_ordinal)' in SQL
    assert 'UNIQUE(release_id, property_id, report_variant, channel)' in SQL
    assert 'ON DELETE CASCADE' not in SQL.upper()


def test_release_items_preserve_exact_downstream_lineage_slots():
    for field in ('target_snapshot_id','target_report_id','target_render_id','target_semantic_fingerprint','target_presentation_fingerprint'):
        assert field in SQL
