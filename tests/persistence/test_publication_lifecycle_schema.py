from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
def test_publication_freeze_and_history_lookup_schema_exists():
    s=(ROOT/'database/migrations/0048_publication_lifecycle.sql').read_text()
    assert 'publication.publication_freezes' in s
    assert 'uq_publication_freeze_active_scope' in s
    assert 'idx_publication_history_lookup' in s

def test_cache_event_seed_is_additive():
    s=(ROOT/'database/migrations/0165_reference_seed_data.sql').read_text()
    assert 'PUBLICATION_CACHE_INVALIDATED' in s and 'ON CONFLICT (code) DO NOTHING' in s
